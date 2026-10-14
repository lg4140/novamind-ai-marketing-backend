from fastapi.testclient import TestClient
from app.main import app

HEAD={'Authorization':'Bearer dev-only-change-me','Idempotency-Key':'api-case-1'}

def test_auth_and_full_demo_flow():
    with TestClient(app) as client:
        assert client.post('/api/v1/campaigns',json={'topic':'AI automation'},headers={}).status_code==401
        response=client.post('/api/v1/contacts/import',headers=HEAD,json=[
          {'email':'demo@example.test','firstname':'Demo','lastname':'User',
           'company':'DemoCo','persona_segment':'ops_lead','marketing_consent':True},
        ])
        assert response.status_code==200, response.text
        created=client.post('/api/v1/campaigns',headers=HEAD,json={'topic':'AI automation'})
        assert created.status_code==202,created.text
        data=created.json()
        assert data['status']=='REVIEW_REQUIRED'
        cid=data['id']
        again=client.post('/api/v1/campaigns',headers=HEAD,json={'topic':'AI automation'})
        assert again.status_code==202 and again.json()['id']==cid
        assert client.get(f'/api/v1/campaigns/{cid}/content',headers=HEAD).status_code==200
        assert client.post(f'/api/v1/campaigns/{cid}/approve',headers=HEAD).json()['status']=='APPROVED'
        assert client.post(f'/api/v1/campaigns/{cid}/dispatch',headers=HEAD).json()['status']=='COMPLETED'
        assert client.post(f'/api/v1/campaigns/{cid}/dispatch',headers=HEAD).status_code==409
        metrics=client.get(f'/api/v1/campaigns/{cid}/metrics',headers=HEAD).json()
        assert metrics['recipient_count']==1 and metrics['open_rate'] is None
        report=client.post(f'/api/v1/campaigns/{cid}/analysis',headers=HEAD).json()
        assert 'no observed delivery' in report['summary'].lower()

def test_no_consent_is_default():
    with TestClient(app) as client:
        contact={'email':'n@example.test','firstname':'N','lastname':'N',
                 'company':'NoCo','persona_segment':'ops_lead'}
        client.post('/api/v1/contacts/import',headers=HEAD,json=[contact])
        c=client.post('/api/v1/campaigns',headers={**HEAD,'Idempotency-Key':'noconsent'},
                      json={'topic':'Workflow tools'}).json()
        client.post(f'/api/v1/campaigns/{c["id"]}/approve',headers=HEAD)
        client.post(f'/api/v1/campaigns/{c["id"]}/dispatch',headers=HEAD)
        m=client.get(f'/api/v1/campaigns/{c["id"]}/metrics',headers=HEAD).json()
        assert m['skipped_no_consent']==1
