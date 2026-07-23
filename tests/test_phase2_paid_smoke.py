"""Explicitly opt-in Yahoo + CIII Phase 2 acceptance flow."""

from __future__ import annotations

import os

import pytest

from tradingagents.persistence import Database, Repository
from tradingagents.usage import paid_tests_enabled

ENABLED, REASON = paid_tests_enabled()
pytestmark = [
    pytest.mark.paid,
    pytest.mark.integration,
    pytest.mark.skipif(not ENABLED, reason=REASON or "paid tests disabled"),
]


def test_paid_spy_analysis_fresh_chat_and_reevaluation(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from tradingagents.web.app import create_app

    quick = os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM")
    deep = os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM")
    if not quick or not deep or not os.environ.get("CIII_API_KEY") or not os.environ.get("TRADINGAGENTS_CIII_BASE_URL"):
        pytest.skip("CIII endpoint, key, and quick/deep model IDs are required")

    repository = Repository(Database(tmp_path / "paid-smoke.sqlite3"))
    app = create_app(demo=False, repository=repository)
    client = TestClient(app)
    created = client.post("/api/analyses", json={
        "symbol": "SPY", "asset_type": "fund", "analysis_date": "2026-07-22",
        "benchmark_symbol": "SPY", "analysts": ["market", "fundamentals"],
        "research_depth": 1, "llm_provider": "ciii", "quick_model": quick,
        "deep_model": deep, "output_language": "English",
    })
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    app.state.jobs.threads[job_id].join(timeout=600)
    state = client.get(f"/api/analyses/{job_id}").json()
    assert state["status"] == "completed", state.get("error")
    usage = client.get(f"/api/analyses/{job_id}/usage").json()["summary"]
    assert 0 < usage["requests"] <= int(os.environ["TRADINGAGENTS_BUDGET_MAX_REQUESTS"])
    assert usage["total_tokens"] <= int(os.environ["TRADINGAGENTS_BUDGET_MAX_TOKENS"])

    conversation = client.post(
        f"/api/reports/{state['report_id']}/conversations"
    ).json()
    reply = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={
            "content": "Using current data, propose a candidate adjustment and explain conflicts.",
            "refresh_data": True,
            "candidate_adjustment": True,
        },
    ).json()
    child = client.post(
        f"/api/conversations/{conversation['id']}/re-evaluate",
        json={"trigger_message_ids": [reply["user"]["id"], reply["assistant"]["id"]]},
    )
    assert child.status_code == 201 and child.json()["version"] == 2
