import pytest
from sqlalchemy import select
from app.db.session import session_factory
from app.db.models import CampaignRecipient
from app.schemas import CampaignCreate, ContactIn
from app.services.campaigns import (ConflictError, approve_campaign,create_campaign,
    import_contacts, process_dispatch, process_generation, retry_campaign)
from app.services.analytics import campaign_metrics,record_demo_event
from app.schemas import DemoEventIn

@pytest.fixture
def records():
    with session_factory()() as db:
        import_contacts(db,[
            ContactIn(email='a@example.test',firstname='A',lastname='One',company='X',persona_segment='ops_lead',marketing_consent=True),
            ContactIn(email='b@example.test',firstname='B',lastname='Two',company='Y',persona_segment='freelancer',marketing_consent=False),
        ])
        yield db

def test_idempotency_and_content_generation(records):
    a,created=create_campaign(records,CampaignCreate(topic='AI content test'),'key1')
    b,created_again=create_campaign(records,CampaignCreate(topic='AI content test'),'key1')
    assert created and not created_again and a.id == b.id
    assert process_generation(records,a.id)
    assert not process_generation(records,a.id)
    assert len(a.content.payload['newsletters']) == 3
    with pytest.raises(ConflictError):
        create_campaign(records,CampaignCreate(topic='Different test'),'key1')

def test_consent_gate_duplicate_dispatch_and_real_metric_nulls(records):
    campaign,_=create_campaign(records,CampaignCreate(topic='AI automation'), 'key2')
    process_generation(records,campaign.id)
    approve_campaign(records,campaign.id)
    assert process_dispatch(records,campaign.id)
    assert not process_dispatch(records,campaign.id)
    rows = records.scalars(select(CampaignRecipient).where(CampaignRecipient.campaign_id==campaign.id)).all()
    assert sorted([r.status for r in rows]) == ['SIMULATED','SKIPPED_NO_CONSENT']
    metrics = campaign_metrics(records,campaign.id)
    assert metrics['open_rate'] is None and metrics['click_rate'] is None
    assert metrics['is_real_world_performance'] is False

def test_demo_event_dedup_and_metric_consistency(records):
    campaign,_=create_campaign(records,CampaignCreate(topic='AI automation'), 'key3')
    process_generation(records,campaign.id)
    approve_campaign(records,campaign.id)
    process_dispatch(records,campaign.id)
    recipient = records.scalar(select(CampaignRecipient).where(CampaignRecipient.status=='SIMULATED'))
    d=DemoEventIn(recipient_id=recipient.id,provider_event_id='event-01',event_type='delivered')
    assert record_demo_event(records,d) is True
    assert record_demo_event(records,d) is False
    record_demo_event(records,DemoEventIn(recipient_id=recipient.id,provider_event_id='event-02',event_type='opened'))
    record_demo_event(records,DemoEventIn(recipient_id=recipient.id,provider_event_id='event-03',event_type='clicked'))
    m=campaign_metrics(records,campaign.id)
    assert m['delivered_count']==1 and m['unique_open_count']==1 and m['open_rate']==1.0
    assert m['event_provenance']=='synthetic_demo'

def test_approval_required(records):
    campaign,_=create_campaign(records,CampaignCreate(topic='AI automation'), 'key4')
    with pytest.raises(ConflictError):
        approve_campaign(records,campaign.id)
    with pytest.raises(ConflictError):
        retry_campaign(records,campaign.id)
