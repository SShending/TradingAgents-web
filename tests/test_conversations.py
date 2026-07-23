from __future__ import annotations

from copy import deepcopy

from tradingagents.persistence import Database, Repository
from tradingagents.services.artifact_service import ArtifactService
from tradingagents.services.conversation_service import ConversationService
from tradingagents.usage import BudgetLimits


def completed_workspace(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    job_record = repository.create_job({
        "symbol": "SPY", "llm_provider": "demo", "quick_model": "demo", "deep_model": "demo",
    })
    result = {
        "company_of_interest": "SPY", "asset_type": "fund", "trade_date": "2026-07-21",
        "benchmark_symbol": "SPY", "final_trade_decision": "Hold with measured exposure.",
        "fund_snapshot": {
            "instrument": {"canonical_symbol": "SPY", "currency": "USD"},
            "profile": {"nav": 640.0, "nav_as_of": "2026-07-21"},
            "price_series": [{"date": "2026-07-21", "adjusted_close": 642.0, "benchmark": 630.0}],
            "top_holdings": [{"symbol": "AAPL", "weight": 0.06}],
            "source": "demo-yfinance", "warnings": [],
        },
    }

    class Job:
        id = job_record.id
        request = job_record.request

    artifacts = ArtifactService(repository).persist_analysis(Job(), result)
    repository.update_job(
        job_record.id, "completed", result=result,
        report_id=artifacts["report_id"], advice_id=artifacts["advice_id"],
    )
    return repository, artifacts


def test_chat_persists_across_service_recreation_without_changing_advice(tmp_path):
    repository, artifacts = completed_workspace(tmp_path)
    service = ConversationService(repository)
    conversation = service.create(artifacts["report_id"])
    before = repository.list_advice(artifacts["report_id"])
    user, assistant = service.ask(conversation.id, "What supports this view?")
    assert "persisted report" in assistant.content
    assert assistant.usage_record_id
    assert repository.list_advice(artifacts["report_id"]) == before

    restarted = ConversationService(repository)
    recovered, messages = restarted.get(conversation.id)
    assert recovered.id == conversation.id
    assert [message.id for message in messages] == [user.id, assistant.id]
    assert len(repository.list_usage(conversation_id=conversation.id)) == 1


def test_fresh_data_is_cited_conflict_marked_and_trust_persisted(tmp_path):
    repository, artifacts = completed_workspace(tmp_path)

    def fresh(report):
        value = deepcopy(report)
        value["trade_date"] = "2026-07-22"
        value["fund_snapshot"]["price_series"].append({
            "date": "2026-07-22", "adjusted_close": 650.0, "benchmark": 632.0,
        })
        return value

    service = ConversationService(repository, fresh_data_fetcher=fresh)
    conversation = service.create(artifacts["report_id"])
    _, assistant = service.ask(conversation.id, "What is the latest price?", refresh_data=True)
    assert assistant.refreshed_data is True and assistant.source_references
    assert "Newer evidence conflicts with the report" in assistant.content
    assert repository.list_observations(conversation_id=conversation.id)
    assert repository.latest_trust(conversation_id=conversation.id)
    assert repository.get_report(artifacts["report_id"]).result["fund_snapshot"]["price_series"][-1]["adjusted_close"] == 642.0


def test_only_explicit_reevaluate_creates_child_formal_version(tmp_path):
    repository, artifacts = completed_workspace(tmp_path)
    service = ConversationService(repository)
    conversation = service.create(artifacts["report_id"])
    user, assistant = service.ask(
        conversation.id, "Candidate adjustment: sell if risk rises.", candidate_adjustment=True
    )
    assert len(repository.list_advice(artifacts["report_id"])) == 1
    child = service.re_evaluate(
        conversation.id, trigger_message_ids=[user.id, assistant.id]
    )
    versions = repository.list_advice(artifacts["report_id"])
    assert len(versions) == 2 and child.version == 2
    assert child.parent_id == versions[0].id
    assert child.trigger_message_ids == (user.id, assistant.id)
    assert child.action == "sell"


def test_chat_redacts_secrets_before_persistence(tmp_path):
    repository, artifacts = completed_workspace(tmp_path)
    service = ConversationService(repository)
    conversation = service.create(artifacts["report_id"])
    user, _ = service.ask(conversation.id, "authorization=secret-value what changed?")
    assert "secret-value" not in user.content and "[redacted]" in user.content


def test_chat_budget_exhaustion_is_stable(tmp_path):
    repository, artifacts = completed_workspace(tmp_path)
    service = ConversationService(
        repository,
        budget_limits=BudgetLimits(0, 100, 0, 1, 10, 1000),
    )
    conversation = service.create(artifacts["report_id"])
    from tradingagents.usage import BudgetExhaustedError
    try:
        service.ask(conversation.id, "Question")
    except BudgetExhaustedError as exc:
        assert exc.code == "BUDGET_EXHAUSTED" and exc.reason == "ANALYSIS_REQUEST_LIMIT"
    else:
        raise AssertionError("expected budget exhaustion")
