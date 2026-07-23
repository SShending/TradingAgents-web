from __future__ import annotations

from tradingagents.persistence import Database, Repository
from tradingagents.services.artifact_service import ArtifactService
from tradingagents.trust import assess_result_evidence


def result(*, price_date="2026-07-21", holdings=True, currency="USD"):
    return {
        "company_of_interest": "SPY",
        "asset_type": "fund",
        "trade_date": "2026-07-21",
        "benchmark_symbol": "SPY",
        "final_trade_decision": "Final Rating: Overweight",
        "fund_snapshot": {
            "instrument": {"canonical_symbol": "SPY", "currency": currency},
            "profile": {"nav": 640.0, "nav_as_of": price_date},
            "price_series": [{"date": price_date, "adjusted_close": 642.0, "benchmark": 630.0}],
            "top_holdings": [{"symbol": "AAPL", "weight": 0.06}] if holdings else [],
            "warnings": [],
            "source": "yfinance",
        },
    }


def test_fresh_complete_yahoo_evidence_is_trusted():
    observation, trust = assess_result_evidence(result())
    assert observation.source == "yfinance" and len(observation.raw_hash) == 64
    assert trust.level == "trusted" and trust.executable is True
    assert {field.name for field in trust.evidence} >= {"instrument_identity", "currency", "cutoff_price"}
    assert {field.name for field in trust.evidence} >= {"profile.nav_as_of", "top_holdings.0", "price_series", "benchmark_series"}


def test_missing_optional_holdings_is_warning_level():
    _, trust = assess_result_evidence(result(holdings=False))
    assert trust.level == "usable_with_warning" and trust.executable is False
    assert "OPTIONAL_HOLDINGS_MISSING" in trust.reason_codes


def test_stale_or_missing_critical_evidence_is_insufficient():
    _, stale = assess_result_evidence(result(price_date="2026-07-15"))
    assert stale.level == "insufficient" and "CUTOFF_PRICE_STALE" in stale.reason_codes
    missing_result = result(currency=None)
    missing_result["fund_snapshot"]["price_series"] = []
    _, missing = assess_result_evidence(missing_result)
    assert missing.level == "insufficient"
    assert {"CURRENCY_MISSING", "CUTOFF_PRICE_MISSING"} <= set(missing.reason_codes)


def test_artifact_service_persists_report_trust_evidence_and_advice(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    job_record = repository.create_job({
        "symbol": "SPY", "llm_provider": "ciii", "quick_model": "quick", "deep_model": "deep",
    })

    class Job:
        id = job_record.id
        request = job_record.request

    payload = result()
    artifacts = ArtifactService(repository).persist_analysis(Job(), payload)
    report = repository.get_report(artifacts["report_id"])
    advice = repository.get_advice(artifacts["advice_id"])
    assert "## Data Quality" in report.markdown
    assert "Trust level: trusted" in report.markdown
    assert report.result["data_quality"]["level"] == "trusted"
    assert repository.list_observations(job_id=job_record.id)
    assert repository.latest_trust(job_id=job_record.id).level == "trusted"
    assert advice.action == "buy" and advice.eligibility == "executable" and advice.version == 1
