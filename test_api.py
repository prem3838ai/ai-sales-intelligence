from fastapi.testclient import TestClient
import api

def test_health():
    assert TestClient(api.app).get('/health').json()['status'] == 'ok'

def test_metrics_empty_or_populated():
    result = TestClient(api.app).get('/metrics')
    assert result.status_code == 200
    assert 'revenue' in result.json()
