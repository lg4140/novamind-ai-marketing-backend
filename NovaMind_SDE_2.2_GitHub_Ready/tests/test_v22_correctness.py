"""Regression proofs for verified 2.1 correctness gaps."""
from datetime import timedelta
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.db.models import Campaign, CampaignRecipient, Contact, DeliveryEvent, OutboxEvent, utcnow
from app.db.session import engine, session_factory
from app.schemas import CampaignCreate, ContactIn, DemoEventIn
from app.services import campaigns
from app.services.analytics import campaign_metrics, record_demo_event
from app.core.config import get_settings
from app.workers import outbox


def setup_campaign(db, key='v22'):
    campaigns.import_contacts(db,[ContactIn(email='first@example.test',firstname='First',lastname='Test',
                            company='Agency', persona_segment='ops_lead',marketing_consent=True)])
    c,_=campaigns.create_campaign(db,CampaignCreate(topic='AI workflow workflows'),key)
    assert campaigns.process_generation(db,c.id)
    campaigns.approve_campaign(db,c.id)
    campaigns.process_dispatch(db,c.id)
    return c


def test_historical_persona_snapshot_unchanged_after_reimport():
    with session_factory()() as db:
        c=setup_campaign(db,'snap-1')
        original=campaign_metrics(db,c.id)
        assert original['by_persona']['ops_lead']['recipient_count']==1
        campaigns.import_contacts(db,[ContactIn(email='first@example.test',firstname='First',lastname='Test',
                             company='Agency',persona_segment='freelancer',marketing_consent=True)])
        updated=campaign_metrics(db,c.id)
        assert updated['by_persona']==original['by_persona']
        recipient=db.scalar(select(CampaignRecipient).where(CampaignRecipient.campaign_id==c.id))
        assert recipient.persona_at_dispatch=='ops_lead'
        assert recipient.snapshot_source=='captured_at_dispatch'
        assert recipient.content_version_id is not None
        assert recipient.consent_at_dispatch is True


def test_sqlite_enforces_foreign_key_references():
    with engine().connect() as conn:
        assert conn.execute(text('PRAGMA foreign_keys')).scalar()==1
    with session_factory()() as db:
        db.add(DeliveryEvent(provider_event_id='fk-test', recipient_id='missing',
                event_type='delivered',source='synthetic_demo'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_unsubscribe_before_delivered_suppresses_future_campaigns():
    with session_factory()() as db:
        c=setup_campaign(db,'unsub-first-v22')
        recipient=db.scalar(select(CampaignRecipient).where(CampaignRecipient.campaign_id==c.id))
        e=DemoEventIn(recipient_id=recipient.id,provider_event_id='unsub-first-event',event_type='unsubscribed')
        assert record_demo_event(db,e)
        assert record_demo_event(db,e) is False
        contact=db.get(Contact,recipient.contact_id)
        assert contact.suppression_reason=='unsubscribed' and contact.marketing_consent is False
        assert record_demo_event(db,DemoEventIn(recipient_id=recipient.id,
               provider_event_id='late-delivery-event',event_type='delivered'))
        second,_=campaigns.create_campaign(db,CampaignCreate(topic='AI workflow workflows'),'after-unsub-v22')
        campaigns.process_generation(db,second.id)
        campaigns.approve_campaign(db,second.id)
        campaigns.process_dispatch(db,second.id)
        assert campaign_metrics(db,second.id)['skipped_no_consent']==1


def test_content_revision_has_separate_budget_from_execution_retry():
    with session_factory()() as db:
        campaigns.import_contacts(db,[])
        c,_=campaigns.create_campaign(db,CampaignCreate(topic='AI workflow workflows'),'rev-v22')
        campaigns.process_generation(db,c.id)
        for index in range(5):
            campaigns.request_revision(db,c.id)
            assert campaigns.process_generation(db,c.id), index
        db.refresh(c)
        assert c.content_revision_count==5
        assert c.generation_retry_count==1
        assert c.attempt==6
        assert len(c.content_versions)==6


def test_lease_renewal_is_fenced():
    with session_factory()() as db:
        c,_=campaigns.create_campaign(db,CampaignCreate(topic='AI workflow workflows'),'lease-v22')
        old_token,_=campaigns._claim(db,c.id,'generation',('QUEUED',))
        assert campaigns.renew_execution_lease(db,c.id,old_token,'generation')
        obj=db.get(Campaign,c.id)
        obj.lease_until=utcnow()-timedelta(seconds=100)
        db.commit()
        assert campaigns.recover_stale(db)==1
        assert not campaigns.renew_execution_lease(db,c.id,old_token,'generation')


def _celery(monkeypatch):
    monkeypatch.setenv('QUEUE_MODE','celery'); get_settings.cache_clear()


def test_outbox_lease_claim_expiry_and_stale_ack_rejection(monkeypatch):
    _celery(monkeypatch)
    with session_factory()() as db:
        c,_=campaigns.create_campaign(db,CampaignCreate(topic='AI workflow workflows'),'ob-v22')
        event=db.scalar(select(OutboxEvent).where(OutboxEvent.payload['campaign_id'].as_string()==c.id))
        event_id=event.id
    first=outbox.claim_pending()
    assert len(first)==1 and first[0][0]==event_id
    assert outbox.claim_pending()==[]
    with session_factory()() as db:
        event=db.get(OutboxEvent,event_id)
        event.lease_until=utcnow()-timedelta(seconds=2)
        db.commit()
    newer=outbox.claim_pending()
    assert newer[0][0]==event_id and newer[0][1]!=first[0][1]
    assert outbox._ack(event_id,first[0][1],None) is False
    assert outbox._ack(event_id,newer[0][1],None)
    with session_factory()() as db:
        row=db.get(OutboxEvent,event_id)
        assert row.status=='PUBLISHED' and row.attempts==1


def test_api_rejects_unknown_request_fields():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CampaignCreate.model_validate({'topic':'AI workflow workflows','mode':'live'})
