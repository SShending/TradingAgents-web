import json
from time import sleep

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
    for _ in range(100):
        state = client.get(f'/api/analyses/{job_id}').json()
        if state['status'] == 'completed':
            break
        sleep(.005)
    assert state['status'] == 'completed'
    stream = client.get(f'/api/analyses/{job_id}/events').text
    ids = [int(line.split(': ')[1]) for line in stream.splitlines() if line.startswith('id:')]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    replay = client.get(f'/api/analyses/{job_id}/events', headers={'Last-Event-ID': str(ids[-2])}).text
    assert f'id: {ids[-1]}' in replay and f'id: {ids[-2]}' not in replay
    report = client.get(f'/api/analyses/{job_id}/report.md')
    assert report.status_code == 200 and '## Fund Analysis' in report.text


def test_busy_cancel_unknown_and_validation():
    client = TestClient(create_app(demo=True, manager=JobManager(DemoAnalysisService(delay=.2))))
    first = client.post('/api/analyses', json=payload()).json()['job_id']
    assert client.post('/api/analyses', json=payload(symbol='AAPL')).status_code == 409
    assert client.post(f'/api/analyses/{first}/cancel').status_code == 200
    for _ in range(100):
        status = client.get(f'/api/analyses/{first}').json()['status']
        if status == 'cancelled':
            break
        sleep(.01)
    assert status == 'cancelled'
    assert client.get('/api/analyses/no-such-job').status_code == 404
    assert client.post('/api/analyses', json=payload(symbol='../secret')).status_code == 422
    assert client.post('/api/analyses', json=payload(analysis_date='2999-01-01')).status_code == 422
