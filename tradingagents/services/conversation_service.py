"""Persistent report Q&A and explicit formal advice re-evaluation."""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol

from tradingagents.domain import AdviceVersion, Conversation, ConversationMessage
from tradingagents.persistence import Repository
from tradingagents.trust import assess_result_evidence
from tradingagents.usage import BudgetTracker, wrap_llm
from tradingagents.usage.budget import summarize_usage

from .artifact_service import deterministic_action

SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|token|secret|password)\s*[:=]?\s*\S+"
)


class ConversationNotFoundError(KeyError):
    pass


class ChatResponder(Protocol):
    def answer(
        self,
        *,
        question: str,
        report: dict[str, Any],
        fresh_result: dict[str, Any] | None,
        candidate_adjustment: bool,
        tracker: BudgetTracker,
    ) -> str: ...


class DeterministicChatResponder:
    def answer(self, *, question: str, report: dict[str, Any], fresh_result: dict[str, Any] | None, candidate_adjustment: bool, tracker: BudgetTracker) -> str:
        tracker.before_request()
        tracker.record(model="deterministic-demo")
        decision = str(report.get("final_trade_decision") or "No formal decision text is available.")
        prefix = "Candidate adjustment only; formal advice is unchanged. " if candidate_adjustment else ""
        freshness = " Fresh data was retrieved and is labelled below." if fresh_result else ""
        return f"{prefix}Based on the persisted report: {decision[:500]}{freshness}"


class LLMChatResponder:
    def __init__(self, *, provider: str, model: str, base_url: str | None = None):
        self.provider = provider
        self.model = model
        self.base_url = base_url

    def answer(self, *, question: str, report: dict[str, Any], fresh_result: dict[str, Any] | None, candidate_adjustment: bool, tracker: BudgetTracker) -> str:
        from tradingagents.llm_clients import create_llm_client

        client = create_llm_client(self.provider, self.model, self.base_url, max_retries=0)
        llm = wrap_llm(client.get_llm(), provider=self.provider, model=self.model)
        prompt = (
            "Answer only from the persisted report and supplied fresh evidence. "
            "Never claim chat changes formal advice. Label any newer evidence.\n\n"
            f"Report: {report}\nFresh evidence: {fresh_result or 'not requested'}\n"
            f"Candidate adjustment requested: {candidate_adjustment}\nQuestion: {question}"
        )
        response = llm.invoke(prompt)
        return str(getattr(response, "content", response))


class ConversationService:
    def __init__(
        self,
        repository: Repository,
        *,
        responder_factory: Callable[[dict[str, Any]], ChatResponder] | None = None,
        fresh_data_fetcher: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        budget_limits=None,
    ):
        self.repository = repository
        self.responder_factory = responder_factory or (lambda _request: DeterministicChatResponder())
        self.fresh_data_fetcher = fresh_data_fetcher
        self.budget_limits = budget_limits

    def create(self, report_id: str) -> Conversation:
        if self.repository.get_report(report_id) is None:
            raise ConversationNotFoundError(report_id)
        return self.repository.create_conversation(report_id)

    def get(self, conversation_id: str) -> tuple[Conversation, list[ConversationMessage]]:
        value = self.repository.get_conversation(conversation_id)
        if value is None:
            raise ConversationNotFoundError(conversation_id)
        return value

    def ask(
        self,
        conversation_id: str,
        content: str,
        *,
        refresh_data: bool = False,
        candidate_adjustment: bool = False,
    ) -> tuple[ConversationMessage, ConversationMessage]:
        conversation, _ = self.get(conversation_id)
        report = self.repository.get_report(conversation.report_id)
        if report is None:
            raise ConversationNotFoundError(conversation.report_id)
        safe_content = self._redact(content)
        user_message = self.repository.add_message(
            conversation_id, "user", safe_content, candidate_adjustment=candidate_adjustment
        )
        fresh_result = None
        source_references: list[str] = []
        conflict = False
        if refresh_data:
            if self.fresh_data_fetcher is None:
                raise RuntimeError("FRESH_DATA_UNAVAILABLE")
            fresh_result = self.fresh_data_fetcher(deepcopy(report.result))
            observation, trust = assess_result_evidence(
                fresh_result, conversation_id=conversation_id
            )
            self.repository.add_observation(observation)
            self.repository.add_trust(trust)
            source_references.append(observation.id)
            conflict = self._materially_changed(report.result, fresh_result)
        job = self.repository.get_job(report.job_id)
        request = job.request if job else {}
        provider = str(request.get("llm_provider") or "demo")
        tracker = BudgetTracker(
            self.repository,
            conversation_id=conversation_id,
            provider=provider,
            limits=self.budget_limits,
        )
        responder = self.responder_factory(request)
        with tracker.activate():
            answer = responder.answer(
                question=safe_content,
                report=report.result,
                fresh_result=fresh_result,
                candidate_adjustment=candidate_adjustment,
                tracker=tracker,
            )
        if refresh_data:
            label = "Newer evidence conflicts with the report." if conflict else "Newer evidence does not materially conflict with the report."
            answer = f"{answer}\n\nFresh-data marker: {label}"
        usage = self.repository.list_usage(conversation_id=conversation_id)
        usage_id = usage[-1].id if usage else None
        assistant = self.repository.add_message(
            conversation_id,
            "assistant",
            self._redact(answer),
            source_references=source_references,
            refreshed_data=refresh_data,
            candidate_adjustment=candidate_adjustment,
            usage_record_id=usage_id,
        )
        return user_message, assistant

    def re_evaluate(
        self,
        conversation_id: str,
        *,
        trigger_message_ids: list[str],
    ) -> AdviceVersion:
        conversation, messages = self.get(conversation_id)
        valid_ids = {message.id for message in messages}
        if not trigger_message_ids or not set(trigger_message_ids) <= valid_ids:
            raise ValueError("INVALID_TRIGGER_MESSAGES")
        report = self.repository.get_report(conversation.report_id)
        if report is None:
            raise ConversationNotFoundError(conversation.report_id)
        versions = self.repository.list_advice(report.id)
        if not versions:
            raise ValueError("FORMAL_ADVICE_NOT_FOUND")
        parent = versions[-1]
        trust = self.repository.latest_trust(conversation_id=conversation_id)
        if trust is None:
            trust = self.repository.latest_trust(job_id=report.job_id)
        observations = self.repository.list_observations(conversation_id=conversation_id)
        observation_id = observations[-1].id if observations else parent.data_snapshot.get("observation_id")
        triggered = [message for message in messages if message.id in trigger_message_ids]
        candidate = next(
            (
                message.content
                for message in reversed(triggered)
                if message.role == "user" and message.candidate_adjustment
            ),
            None,
        )
        evaluation_result = deepcopy(report.result)
        if candidate:
            evaluation_result["final_trade_decision"] = candidate
        usage = summarize_usage(self.repository.list_usage(conversation_id=conversation_id))
        return self.repository.create_advice(
            report.id,
            action=deterministic_action(evaluation_result),
            confidence="medium" if trust and trust.level == "trusted" else "low",
            reason="Explicit re-evaluation from persisted conversation context.",
            eligibility="executable" if trust and trust.executable else "observation_only",
            parent_id=parent.id,
            trust_assessment_id=trust.id if trust else None,
            trigger_message_ids=trigger_message_ids,
            data_snapshot={"observation_id": observation_id},
            model_config=parent.model_config,
            usage=usage,
        )

    @staticmethod
    def _redact(value: str) -> str:
        return SECRET_RE.sub("[redacted]", value)[:20_000]

    @staticmethod
    def _materially_changed(original: dict[str, Any], fresh: dict[str, Any]) -> bool:
        def latest_price(value: dict[str, Any]) -> Any:
            points = (value.get("fund_snapshot") or {}).get("price_series") or []
            return points[-1].get("adjusted_close") if points else None

        return latest_price(original) != latest_price(fresh)
