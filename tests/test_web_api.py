import json
from threading import Event

import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient

from tradingagents.services.analysis_service import DemoAnalysisService
from tradingagents.web.app import create_app
from tradingagents.web.jobs import JobManager


@pytest.fixture
def client():
    return TestClient(create_app(demo=True, manager=JobManager(DemoAnalysisService(delay=0))))


def payload(**overrides):
    values = {"symbol":"SPY","asset_type":"auto","analysis_date":"2026-07-21","benchmark_symbol":"SPY","analysts":["market","social","news","fundamentals"],"research_depth":1,"llm_provider":"openai","quick_model":"demo","deep_model":"demo","output_language":"English"}
    values.update(overrides)
    return values


def test_health_safe_config_and_resolution(client):
    assert client.get('/api/health').json() == {"status":"ok","mode":"demo"}
    options = client.get('/api/config/options').json()
    assert 'providers' in options
    assert 'api_key' not in json.dumps(options).lower()
    spy = client.post('/api/instruments/resolve', json={"symbol":"SPY","asset_type":"auto"}).json()
    assert spy['asset_type'] == 'fund' and spy['fund_type'] == 'etf'
    conflict = client.post('/api/instruments/resolve', json={"symbol":"SPY","asset_type":"stock"}).json()
    assert conflict['warnings']


def test_create_complete_sse_replay_and_report(client):
    created = client.post('/api/analyses', json=payload())
    assert created.status_code == 202
    job_id = created.json()['job_id']
    client.app.state.jobs.threads[job_id].join(timeout=2)
    state = client.get(f'/api/analyses/{job_id}').json()
    assert state['status'] == 'completed'
    stream = client.get(f'/api/analyses/{job_id}/events').text
    ids = [int(line.split(': ')[1]) for line in stream.splitlines() if line.startswith('id:')]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    replay = client.get(f'/api/analyses/{job_id}/events', headers={'Last-Event-ID': str(ids[-2])}).text
    assert f'id: {ids[-1]}' in replay and f'id: {ids[-2]}' not in replay
    report = client.get(f'/api/analyses/{job_id}/report.md')
    assert report.status_code == 200 and '## Fund Analysis' in report.text


def test_busy_cancel_unknown_and_validation():
    started = Event()

    class CancellableService:
        def execute(self, request, emit, should_cancel):
            from tradingagents.services.analysis_service import AnalysisCancelledError
            emit('analysis.started', {})
            started.set()
            while not should_cancel():
                started.wait(0.01)
            raise AnalysisCancelledError

    client = TestClient(create_app(demo=True, manager=JobManager(CancellableService())))
    first = client.post('/api/analyses', json=payload()).json()['job_id']
    assert started.wait(1)
    assert client.post('/api/analyses', json=payload(symbol='AAPL')).status_code == 409
    assert client.post(f'/api/analyses/{first}/cancel').status_code == 200
    client.app.state.jobs.threads[first].join(timeout=2)
    status = client.get(f'/api/analyses/{first}').json()['status']
    assert status == 'cancelled'
    assert client.get('/api/analyses/no-such-job').status_code == 404
    assert client.post('/api/analyses', json=payload(symbol='../secret')).status_code == 422
    assert client.post('/api/analyses', json=payload(analysis_date='2999-01-01')).status_code == 422


def test_failure_response_redacts_secrets_and_local_paths():
    class FailingService:
        def execute(self, request, emit, should_cancel):
            raise RuntimeError('/home/private/config.env api_key=top-secret')

    client = TestClient(create_app(demo=True, manager=JobManager(FailingService())))
    job_id = client.post('/api/analyses', json=payload()).json()['job_id']
    client.app.state.jobs.threads[job_id].join(timeout=2)
    body = json.dumps(client.get(f'/api/analyses/{job_id}').json())
    assert '/home/' not in body and 'top-secret' not in body
    assert '[local path]' in body and '[redacted]' in body
