from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from tradingagents.persistence import Database, Repository
from tradingagents.web.app import create_app


@pytest.fixture
def client(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    return TestClient(create_app(demo=True, repository=repository))


def test_search_resolve_snapshot_trust_and_sources(client):
    search = client.get("/api/funds/search", params={"q": "示例稳健混合"}).json()
    assert len(search["items"]) == 2
    ambiguous = client.post("/api/funds/resolve", json={"query": "示例稳健混合"})
    assert ambiguous.status_code == 409
    assert ambiguous.json()["detail"]["code"] == "IDENTITY_AMBIGUOUS"

    identity = client.post("/api/funds/resolve", json={"query": "900201"}).json()
    assert identity["code"] == "900201" and identity["share_class"] == "A"
    snapshot = client.get(
        "/api/funds/900201/snapshot", params={"analysis_date": date.today().isoformat()}
    ).json()
    assert snapshot["nav_history"] and snapshot["trust"]["critical_ready"] is True
    assert client.get("/api/funds/900201/trust").json()["level"] == "trusted"
    assert client.get("/api/funds/900201/sources").json()["items"]


def test_provider_backed_resolution_is_not_limited_to_a_checked_in_catalog(client):
    identity = client.post("/api/funds/resolve", json={"query": "900101"})
    assert identity.status_code == 200
    assert identity.json()["display_name"] == "示例全球指数(QDII)C"


def test_evaluate_persists_only_executable_formal_advice(client):
    blocked = client.post(
        "/api/funds/900201/evaluate", json={"intended_action": "subscribe"}
    ).json()
    assert blocked["evaluation"]["executable"] is False
    assert blocked["formal_advice"] is None

    first = client.post(
        "/api/funds/900201/evaluate",
        json={"intended_action": "subscribe", "amount": "1000"},
    ).json()
    assert first["evaluation"]["executable"] is True
    assert first["evaluation"]["supporting_evidence"]
    assert first["evaluation"]["friction"]
    assert first["formal_advice"]["version"] == 1
    second = client.post("/api/funds/900201/evaluate", json={"intended_action": "hold"}).json()
    assert second["formal_advice"]["parent_id"] == first["formal_advice"]["id"]


def test_conversion_check_requires_explicit_platform_confirmation(client):
    blocked = client.post(
        "/api/funds/900001/conversion-check",
        json={
            "target_code": "900002",
            "sales_platform": "fixture",
            "conversion_supported": False,
        },
    ).json()
    assert not blocked["executable"]
    assert "PLATFORM_CONVERSION_UNCONFIRMED" in blocked["blocked_reasons"]
    allowed = client.post(
        "/api/funds/900001/conversion-check",
        json={
            "target_code": "900002",
            "sales_platform": "fixture",
            "conversion_supported": True,
            "confirmed_units": "100",
            "holding_days": 90,
            "minimum_holding_known": True,
        },
    ).json()
    assert allowed["executable"]


def test_six_digit_analysis_uses_china_fund_preflight_without_yahoo(client):
    created = client.post(
        "/api/analyses",
        json={
            "symbol": "900101",
            "asset_type": "auto",
            "analysis_date": date.today().isoformat(),
            "benchmark_symbol": "SPY",
            "analysts": ["market", "fundamentals"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_model": "demo",
            "deep_model": "demo",
            "output_language": "Chinese",
        },
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    client.app.state.jobs.threads[job_id].join(timeout=3)
    job = client.get(f"/api/analyses/{job_id}").json()
    assert job["status"] == "completed"
    assert job["result"]["china_fund_snapshot"]["identity"]["code"] == "900101"
    assert job["result"]["fund_snapshot"]["instrument"]["currency"] == "CNY"
    trust = client.get(f"/api/analyses/{job_id}/trust").json()
    assert trust["evidence"] and trust["executable"] is True
