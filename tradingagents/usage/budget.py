"""Request/token/retry budgets enforced before provider calls."""

from __future__ import annotations

import contextlib
import contextvars
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import Runnable

from tradingagents.domain import UsageRecord
from tradingagents.persistence import Repository

_active_tracker: contextvars.ContextVar[BudgetTracker | None] = contextvars.ContextVar(
    "tradingagents_budget_tracker", default=None
)


class BudgetExhaustedError(RuntimeError):
    code = "BUDGET_EXHAUSTED"

    def __init__(self, reason: str, *, partial_result: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.partial_result = partial_result or {}


@dataclass(frozen=True)
class BudgetLimits:
    max_requests_per_analysis: int = 60
    max_total_tokens_per_analysis: int = 200_000
    max_retries_per_request: int = 1
    max_debate_rounds: int = 3
    daily_request_limit: int = 500
    daily_token_limit: int = 1_000_000

    @classmethod
    def from_env(cls) -> BudgetLimits:
        def value(name: str, default: int) -> int:
            raw = os.getenv(name)
            try:
                parsed = int(raw) if raw is not None else default
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if parsed < 0:
                raise ValueError(f"{name} must be non-negative")
            return parsed

        return cls(
            max_requests_per_analysis=value("TRADINGAGENTS_BUDGET_MAX_REQUESTS", 60),
            max_total_tokens_per_analysis=value("TRADINGAGENTS_BUDGET_MAX_TOKENS", 200_000),
            max_retries_per_request=value("TRADINGAGENTS_BUDGET_MAX_RETRIES", 1),
            max_debate_rounds=value("TRADINGAGENTS_BUDGET_MAX_DEBATE_ROUNDS", 3),
            daily_request_limit=value("TRADINGAGENTS_BUDGET_DAILY_REQUESTS", 500),
            daily_token_limit=value("TRADINGAGENTS_BUDGET_DAILY_TOKENS", 1_000_000),
        )

    def public(self) -> dict[str, int]:
        return asdict(self)


def paid_tests_enabled() -> tuple[bool, str | None]:
    if os.getenv("TRADINGAGENTS_ENABLE_PAID_TESTS") != "1":
        return False, "TRADINGAGENTS_ENABLE_PAID_TESTS is not enabled"
    required = (
        "TRADINGAGENTS_BUDGET_MAX_REQUESTS",
        "TRADINGAGENTS_BUDGET_MAX_TOKENS",
        "TRADINGAGENTS_BUDGET_MAX_RETRIES",
    )
    missing = [name for name in required if os.getenv(name) is None]
    if missing:
        return False, f"paid test limits are missing: {', '.join(missing)}"
    limits = BudgetLimits.from_env()
    if limits.max_requests_per_analysis <= 0 or limits.max_total_tokens_per_analysis <= 0:
        return False, "paid test request and token limits must be positive"
    return True, None


class BudgetTracker:
    def __init__(
        self,
        repository: Repository,
        *,
        job_id: str | None = None,
        conversation_id: str | None = None,
        provider: str,
        limits: BudgetLimits | None = None,
    ):
        self.repository = repository
        self.job_id = job_id
        self.conversation_id = conversation_id
        self.provider = provider
        self.limits = limits or BudgetLimits.from_env()
        self._requests = 0
        self._tokens = 0
        self._token_usage_known = True

    @contextlib.contextmanager
    def activate(self):
        token = _active_tracker.set(self)
        try:
            yield self
        finally:
            _active_tracker.reset(token)

    def validate_depth(self, rounds: int) -> None:
        if rounds > self.limits.max_debate_rounds:
            raise BudgetExhaustedError("MAX_DEBATE_ROUNDS_EXCEEDED")

    def before_request(self) -> None:
        daily = self._daily_totals()
        if self._requests >= self.limits.max_requests_per_analysis:
            raise BudgetExhaustedError("ANALYSIS_REQUEST_LIMIT")
        if daily["requests"] >= self.limits.daily_request_limit:
            raise BudgetExhaustedError("DAILY_REQUEST_LIMIT")
        if self._tokens >= self.limits.max_total_tokens_per_analysis:
            raise BudgetExhaustedError("ANALYSIS_TOKEN_LIMIT")
        if daily["tokens"] >= self.limits.daily_token_limit:
            raise BudgetExhaustedError("DAILY_TOKEN_LIMIT")
        self._requests += 1

    def record(
        self,
        *,
        model: str,
        response: Any = None,
        retry: int = 0,
        latency_ms: int = 0,
        status: str = "completed",
    ) -> UsageRecord:
        input_tokens, output_tokens = _extract_tokens(response)
        warning = None
        if input_tokens is None or output_tokens is None:
            input_tokens = output_tokens = None
            self._token_usage_known = False
            warning = "TOKEN_USAGE_UNAVAILABLE_REQUEST_LIMIT_ONLY"
        else:
            self._tokens += input_tokens + output_tokens
        record = UsageRecord(
            str(uuid.uuid4()), self.job_id, self.conversation_id, self.provider, model,
            1, input_tokens, output_tokens, retry, latency_ms, status, warning,
            datetime.now(UTC).isoformat(),
        )
        self.repository.add_usage(record)
        return record

    def summary(self) -> dict[str, Any]:
        records = self.repository.list_usage(job_id=self.job_id, conversation_id=self.conversation_id)
        return summarize_usage(records, limits=self.limits)

    def preflight(self) -> dict[str, Any]:
        historical = self.repository.list_usage()
        completed_groups: dict[str, list[UsageRecord]] = {}
        for record in historical:
            if record.job_id:
                completed_groups.setdefault(record.job_id, []).append(record)
        totals = [summarize_usage(records) for records in completed_groups.values()]
        estimate = None
        if totals:
            estimate = {
                "requests": round(sum(item["requests"] for item in totals) / len(totals), 1),
                "tokens": round(sum(item["total_tokens"] for item in totals) / len(totals), 1),
                "basis": len(totals),
            }
        return {
            "limits": self.limits.public(),
            "historical_estimate": estimate,
            "monetary_estimate": "unknown",
            "daily_usage": self._daily_totals(),
        }

    def _daily_totals(self) -> dict[str, int]:
        start = datetime.now(UTC).date().isoformat()
        records = [
            record for record in self.repository.list_usage(since=start)
            if record.provider == self.provider
        ]
        return {
            "requests": sum(record.requests for record in records),
            "tokens": sum((record.input_tokens or 0) + (record.output_tokens or 0) for record in records),
        }


def summarize_usage(records: list[UsageRecord], *, limits: BudgetLimits | None = None) -> dict[str, Any]:
    input_tokens = sum(record.input_tokens or 0 for record in records)
    output_tokens = sum(record.output_tokens or 0 for record in records)
    return {
        "requests": sum(record.requests for record in records),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "retries": sum(record.retries for record in records),
        "token_usage_complete": all(record.input_tokens is not None for record in records),
        "warnings": sorted({record.warning for record in records if record.warning}),
        "limits": limits.public() if limits else None,
    }


def _extract_tokens(response: Any) -> tuple[int | None, int | None]:
    metadata = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    metadata = metadata or response_metadata.get("token_usage") or response_metadata.get("usage") or {}
    input_tokens = metadata.get("input_tokens", metadata.get("prompt_tokens"))
    output_tokens = metadata.get("output_tokens", metadata.get("completion_tokens"))
    if input_tokens is None or output_tokens is None:
        return None, None
    return int(input_tokens), int(output_tokens)


class BudgetedRunnable(Runnable):
    def __init__(self, runnable: Any, tracker: BudgetTracker, model: str):
        self.runnable = runnable
        self.tracker = tracker
        self.model = model

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for retry in range(self.tracker.limits.max_retries_per_request + 1):
            self.tracker.before_request()
            started = time.monotonic()
            try:
                response = self.runnable.invoke(input, config=config, **kwargs)
                self.tracker.record(
                    model=self.model,
                    response=response,
                    retry=retry,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
                return response
            except BudgetExhaustedError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry at provider boundary
                last_error = exc
                self.tracker.record(
                    model=self.model,
                    retry=retry,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    status="retry" if retry < self.tracker.limits.max_retries_per_request else "failed",
                )
        raise last_error  # type: ignore[misc]

    def stream(self, input: Any, config: Any = None, **kwargs: Any):
        self.tracker.before_request()
        started = time.monotonic()
        try:
            yield from self.runnable.stream(input, config=config, **kwargs)
            self.tracker.record(model=self.model, latency_ms=int((time.monotonic() - started) * 1000))
        except Exception:
            self.tracker.record(
                model=self.model,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="failed",
            )
            raise

    def bind_tools(self, *args: Any, **kwargs: Any) -> BudgetedRunnable:
        return BudgetedRunnable(self.runnable.bind_tools(*args, **kwargs), self.tracker, self.model)

    def with_structured_output(self, *args: Any, **kwargs: Any) -> BudgetedRunnable:
        return BudgetedRunnable(
            self.runnable.with_structured_output(*args, **kwargs), self.tracker, self.model
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.runnable, name)


def wrap_llm(llm: Any, *, provider: str, model: str) -> Any:
    tracker = _active_tracker.get()
    if tracker is None:
        return llm
    if tracker.provider != provider:
        raise ValueError("Budget tracker provider does not match LLM provider")
    return BudgetedRunnable(llm, tracker, model)
