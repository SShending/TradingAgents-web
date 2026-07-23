from __future__ import annotations

import pytest

from tradingagents.persistence import Database, Repository
from tradingagents.services.analysis_service import DemoAnalysisService
from tradingagents.web.jobs import JobManager, JobResumeError


def wait_for(manager, job_id, expected="completed"):
    manager.threads[job_id].join(timeout=2)
    job = manager.get(job_id)
    assert job.status == expected
    return job


def test_job_result_and_sse_replay_survive_manager_recreation(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    manager = JobManager(DemoAnalysisService(delay=0), repository=repository)
    job = manager.create({
        "symbol": "SPY", "asset_type": "fund", "analysis_date": "2026-07-21",
        "benchmark_symbol": "SPY", "analysts": ["market", "social", "news", "fundamentals"],
    })
    wait_for(manager, job.id)
    last_id = repository.list_events(job.id)[-2].event_id

    restarted = JobManager(DemoAnalysisService(delay=0), repository=repository)
    recovered = restarted.get(job.id)
    assert recovered.status == "completed"
    assert recovered.result["company_of_interest"] == "SPY"
    replay = "".join(restarted.event_stream(recovered, last_id))
    assert f"id: {last_id + 1}" in replay
    assert f"id: {last_id}\n" not in replay


def test_restart_marks_stale_job_interrupted_and_resume_is_explicit(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    stale = repository.create_job({"symbol": "SPY"})
    repository.update_job(stale.id, "running")
    manager = JobManager(
        DemoAnalysisService(delay=0),
        repository=repository,
        checkpoint_validator=lambda record: record.run_signature == stale.run_signature,
    )
    job = manager.get(stale.id)
    assert job.status == "interrupted" and job.public()["resumable"] is True
    assert repository.list_events(stale.id)[-1].event_type == "analysis.interrupted"

    manager.resume(job)
    wait_for(manager, stale.id, "failed")


def test_invalid_checkpoint_never_resumes_or_spends_work(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    stale = repository.create_job({"symbol": "SPY"})
    repository.update_job(stale.id, "running")
    manager = JobManager(DemoAnalysisService(delay=0), repository=repository)
    with pytest.raises(JobResumeError, match="No valid checkpoint"):
        manager.resume(manager.get(stale.id))
    assert manager.get(stale.id).status == "interrupted"


def test_event_retention_preserves_terminal_event(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))
    job = repository.create_job({"symbol": "SPY"})
    for number in range(20):
        repository.append_event(job.id, "report.updated", {"number": number})
    repository.append_event(job.id, "analysis.completed", {"status": "completed"})
    repository.trim_events(job.id, keep=5)
    events = repository.list_events(job.id)
    assert len([event for event in events if event.event_type == "report.updated"]) <= 5
    assert events[-1].event_type == "analysis.completed"


def test_graceful_shutdown_marks_inflight_job_interrupted(tmp_path):
    repository = Repository(Database(tmp_path / "workspace.sqlite3"))

    class BlockingService:
        def execute(self, request, emit, should_cancel):
            emit("analysis.started", {})
            while not should_cancel():
                pass
            from tradingagents.services.analysis_service import AnalysisCancelledError
            raise AnalysisCancelledError

    manager = JobManager(BlockingService(), repository=repository)
    job = manager.create({"symbol": "SPY"})
    manager.shutdown(timeout=1)
    assert repository.get_job(job.id).status == "interrupted"
