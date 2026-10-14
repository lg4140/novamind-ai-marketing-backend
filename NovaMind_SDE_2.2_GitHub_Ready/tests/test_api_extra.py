from fastapi.testclient import TestClient
from app.main import app

AUTH={'Authorization':'Bearer dev-only-change-me'}

def test_demo_event_endpoint_and_analysis():
    with TestClient(app) as client:
        imported=client.post('/api/v1/contacts/import',headers=AUTH,json=[
            {'email':'events@example.test','firstname':'Event','lastname':'Tester',
             'company':'Studio','persona_segment':'creative_director','marketing_consent':True}])
        assert imported.status_code==200
        c=client.post('/api/v1/campaigns',headers={**AUTH,'Idempotency-Key':'events-1'},
                      json={'topic':'AI process automation'}).json()
        cid=c['id']
        assert client.get('/api/v1/campaigns/does-not-exist',headers=AUTH).status_code==404
        assert client.get(f'/api/v1/campaigns/{cid}/content',headers=AUTH).status_code==200
        assert client.post(f'/api/v1/campaigns/{cid}/dispatch',headers=AUTH).status_code==409
        assert client.post(f'/api/v1/campaigns/{cid}/approve',headers=AUTH).status_code==200
        assert client.post(f'/api/v1/campaigns/{cid}/dispatch',headers=AUTH).status_code==200
        recipient=client.get(f'/api/v1/campaigns/{cid}/recipients',headers=AUTH).json()[0]['id']
        opened={'recipient_id':recipient,'provider_event_id':'open-1','event_type':'opened'}
        assert client.post('/api/v1/events/demo',headers=AUTH,json=opened).status_code==200
        delivered={'recipient_id':recipient,'provider_event_id':'delivery-1','event_type':'delivered'}
        assert client.post('/api/v1/events/demo',headers=AUTH,json=delivered).json()=={'created':True}
        assert client.post('/api/v1/events/demo',headers=AUTH,json=delivered).json()=={'created':False}
        assert client.post('/api/v1/events/demo',headers=AUTH,json=opened).json()=={'created':False}
        metrics=client.get(f'/api/v1/campaigns/{cid}/metrics',headers=AUTH).json()
        assert metrics['open_rate']==1.0 and metrics['event_provenance']=='synthetic_demo'
        summary=client.post(f'/api/v1/campaigns/{cid}/analysis',headers=AUTH).json()
        assert 'synthetic' in summary['summary'].lower()
        assert client.post('/api/v1/contacts/sync-crm',headers=AUTH).json()['mode']=='mock'

def test_cancel_flow_and_conflict():
    with TestClient(app) as client:
        c=client.post('/api/v1/campaigns',headers={**AUTH,'Idempotency-Key':'cancel-1'},
                      json={'topic':'AI studio workflow'}).json()
        cid=c['id']
        cancelled=client.post(f'/api/v1/campaigns/{cid}/cancel',headers=AUTH)
        assert cancelled.json()['status']=='CANCELLED'
        assert client.post(f'/api/v1/campaigns/{cid}/approve',headers=AUTH).status_code==409
        assert client.post(f'/api/v1/campaigns/{cid}/retry',headers=AUTH).status_code==409
