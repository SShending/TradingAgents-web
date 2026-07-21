"""Bounded in-memory analysis jobs with replayable ordered events."""

from __future__ import annotations

import json
import re
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from tradingagents.services.analysis_service import AnalysisCancelledError, AnalysisService

SECRET_RE = re.compile(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]?\s*\S+")


class JobBusyError(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    request: dict[str, Any]
    status: str = "queued"
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=512))
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    cancel_requested: bool = False
    event_counter: int = 0
    condition: threading.Condition = field(default_factory=threading.Condition)

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        with self.condition:
            self.event_counter += 1
            self.events.append({
                "id": self.event_counter,
                "job_id": self.id,
                "type": event_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "data": data,
            })
            self.condition.notify_all()

    def public(self) -> dict[str, Any]:
        return {"job_id": self.id, "status": self.status, "result": self.result, "error": self.error}


class JobManager:
    def __init__(self, service: AnalysisService, max_active: int = 1):
        self.service = service
        self.max_active = max_active
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def create(self, request: dict[str, Any]) -> Job:
        with self.lock:
            active = sum(job.status in {"queued", "running", "cancelling"} for job in self.jobs.values())
            if active >= self.max_active:
                raise JobBusyError("Another analysis is already running")
            job = Job(str(uuid.uuid4()), request)
            self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True, name=f"analysis-{job.id[:8]}").start()
        return job

    def _run(self, job: Job) -> None:
        job.status = "running"
        try:
            job.result = self.service.execute(job.request, job.emit, lambda: job.cancel_requested)
            if job.cancel_requested:
                raise AnalysisCancelledError
            job.status = "completed"
            job.emit("analysis.completed", {"status": job.status, "result": job.result})
        except AnalysisCancelledError:
            job.status = "cancelled"
            job.emit("analysis.cancelled", {"status": job.status})
        except Exception as exc:  # noqa: BLE001 - convert to safe application error
            safe = SECRET_RE.sub("[redacted]", str(exc))[:300]
            job.status = "failed"
            job.error = {"code": "ANALYSIS_FAILED", "message": safe or "Analysis failed"}
            job.emit("analysis.failed", job.error)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel(self, job: Job) -> None:
        if job.status in {"completed", "failed", "cancelled"}:
            return
        job.cancel_requested = True
        job.status = "cancelling"

    def event_stream(self, job: Job, last_id: int = 0):
        cursor = last_id
        while True:
            with job.condition:
                available = [event for event in job.events if event["id"] > cursor]
                if not available and job.status not in {"completed", "failed", "cancelled"}:
                    job.condition.wait(timeout=15)
                    available = [event for event in job.events if event["id"] > cursor]
                if not available:
                    if job.status in {"completed", "failed", "cancelled"}:
                        return
                    yield ": heartbeat\n\n"
                    continue
            for event in available:
                cursor = event["id"]
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {payload}\n\n"
