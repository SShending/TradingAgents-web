from __future__ import annotations

from types import SimpleNamespace

import pytest

from tradingagents.persistence import Database, Repository
from tradingagents.usage import (
    BudgetExhaustedError,
    BudgetLimits,
    BudgetTracker,
    paid_tests_enabled,
)
from tradingagents.usage.budget import BudgetedRunnable
from tradingagents.web.jobs import JobManager


class FakeRunnable:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    def invoke(self, _input, config=None, **_kwargs):
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def limits(**overrides):
    values = {
        "max_requests_per_analysis": 3,
        "max_total_tokens_per_analysis": 100,
        "max_retries_per_request": 1,
        "max_debate_rounds": 2,
        "daily_request_limit": 10,
        "daily_token_limit": 1000,
    }
    values.update(overrides)
    return BudgetLimits(**values)


def response(input_tokens=10, output_tokens=5):
    return SimpleNamespace(
        content="ok",
        usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens},
    )


def test_exact_request_limit_and_authoritative_token_usage(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    job = repository.create_job({"symbol": "SPY"})
    tracker = BudgetTracker(repository, job_id=job.id, provider="openai", limits=limits(max_requests_per_analysis=2))
    runnable = BudgetedRunnable(FakeRunnable([response(), response()]), tracker, "model")
    runnable.invoke("one")
    runnable.invoke("two")
    with pytest.raises(BudgetExhaustedError, match="ANALYSIS_REQUEST_LIMIT"):
        runnable.invoke("three")
    summary = tracker.summary()
    assert summary["requests"] == 2 and summary["total_tokens"] == 30
    assert summary["token_usage_complete"] is True


def test_retry_counts_as_request_and_is_persisted_without_sleep(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    tracker = BudgetTracker(repository, provider="ciii", limits=limits())
    runnable = BudgetedRunnable(FakeRunnable([RuntimeError("transient"), response()]), tracker, "ciii-model")
    assert runnable.invoke("question").content == "ok"
    summary = tracker.summary()
    assert summary["requests"] == 2
    assert summary["retries"] == 1
    assert [record.status for record in repository.list_usage()] == ["retry", "completed"]


def test_missing_tokens_warns_and_falls_back_to_request_budget(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    tracker = BudgetTracker(repository, provider="ciii", limits=limits(max_requests_per_analysis=1))
    runnable = BudgetedRunnable(FakeRunnable([SimpleNamespace(content="ok")]), tracker, "model")
    runnable.invoke("question")
    summary = tracker.summary()
    assert summary["token_usage_complete"] is False
    assert summary["warnings"] == ["TOKEN_USAGE_UNAVAILABLE_REQUEST_LIMIT_ONLY"]
    with pytest.raises(BudgetExhaustedError):
        runnable.invoke("again")


def test_daily_budget_includes_prior_jobs(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    first = BudgetTracker(repository, provider="ciii", limits=limits(daily_request_limit=1))
    BudgetedRunnable(FakeRunnable([response()]), first, "model").invoke("one")
    second = BudgetTracker(repository, provider="ciii", limits=limits(daily_request_limit=1))
    with pytest.raises(BudgetExhaustedError, match="DAILY_REQUEST_LIMIT"):
        BudgetedRunnable(FakeRunnable([]), second, "model").invoke("two")


def test_preflight_is_unknown_cost_and_uses_history(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    job = repository.create_job({"symbol": "SPY"})
    tracker = BudgetTracker(repository, job_id=job.id, provider="ciii", limits=limits())
    BudgetedRunnable(FakeRunnable([response()]), tracker, "model").invoke("one")
    other = BudgetTracker(repository, provider="ciii", limits=limits())
    preflight = other.preflight()
    assert preflight["monetary_estimate"] == "unknown"
    assert preflight["historical_estimate"] == {"requests": 1.0, "tokens": 15.0, "basis": 1}


def test_budget_exhaustion_persists_partial_result_and_stable_state(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))

    class PartialService:
        def execute(self, request, emit, should_cancel):
            emit("report.updated", {"section": "market_report", "content": "partial"})
            raise BudgetExhaustedError(
                "ANALYSIS_REQUEST_LIMIT", partial_result={"market_report": "partial"}
            )

    def persist_partial(job, result):
        report = repository.create_report(job.id, result, "# Partial\n\npartial")
        return {"report_id": report.id}

    manager = JobManager(
        PartialService(), repository=repository, completion_handler=persist_partial
    )
    job = manager.create({"symbol": "SPY"})
    manager.threads[job.id].join()
    recovered = repository.get_job(job.id)
    assert recovered.status == "budget_exhausted"
    assert recovered.error["code"] == "BUDGET_EXHAUSTED"
    assert recovered.result == {"market_report": "partial"}
    assert repository.get_report_for_job(job.id).markdown.startswith("# Partial")


def test_paid_tests_require_explicit_opt_in_and_all_limits(monkeypatch):
    for name in (
        "TRADINGAGENTS_ENABLE_PAID_TESTS", "TRADINGAGENTS_BUDGET_MAX_REQUESTS",
        "TRADINGAGENTS_BUDGET_MAX_TOKENS", "TRADINGAGENTS_BUDGET_MAX_RETRIES",
    ):
        monkeypatch.delenv(name, raising=False)
    assert paid_tests_enabled()[0] is False
    monkeypatch.setenv("TRADINGAGENTS_ENABLE_PAID_TESTS", "1")
    assert paid_tests_enabled()[0] is False
    monkeypatch.setenv("TRADINGAGENTS_BUDGET_MAX_REQUESTS", "2")
    monkeypatch.setenv("TRADINGAGENTS_BUDGET_MAX_TOKENS", "100")
    monkeypatch.setenv("TRADINGAGENTS_BUDGET_MAX_RETRIES", "0")
    assert paid_tests_enabled() == (True, None)
