from fastapi.testclient import TestClient
from app.main import app

TOKEN = {'Authorization': 'Bearer dev-only-change-me'}


def test_executions_api_exposes_states_without_recipient_pii():
    with TestClient(app) as client:
        response = client.post('/api/v1/campaigns', headers={
            **TOKEN, 'Idempotency-Key': 'executions-1'},
            json={'topic': 'Creative workflow automation'})
        assert response.status_code == 202
        cid = response.json()['id']
        history = client.get(f'/api/v1/campaigns/{cid}/executions', headers=TOKEN)
        assert history.status_code == 200
        assert history.json()[0]['stage'] == 'generation'
        assert history.json()[0]['status'] == 'SUCCEEDED'
        assert 'email' not in str(history.json())
        assert client.get(f'/api/v1/campaigns/{cid}/executions').status_code == 401
