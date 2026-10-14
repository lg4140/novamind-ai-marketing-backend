"""Regression tests for verified v2.0 production-path defects."""
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.db.models import Campaign, CampaignRecipient, Contact, ContentVersion, ExecutionAttempt, utcnow
from app.db.session import session_factory
from app.schemas import CampaignCreate, ContactIn, DemoEventIn
from app.services import campaigns
from app.services.analytics import campaign_metrics, record_demo_event


def _new(db, key='test-campaign'):
    contact = ContactIn(email='alice@example.test', firstname='Alice', lastname='Demo',
        company='Fictional', persona_segment='ops_lead', marketing_consent=True)
    campaigns.import_contacts(db, [contact])
    obj, _ = campaigns.create_campaign(db, CampaignCreate(topic='AI workflow optimization'), key)
    assert campaigns.process_generation(db, obj.id)
    campaigns.approve_campaign(db, obj.id)
    return obj


def test_dispatch_failure_retry_reuses_approved_version(monkeypatch):
    with session_factory()() as db:
        obj = _new(db)
        original = campaigns.MockMailer.send
        def fail(*_):
            raise RuntimeError('temporary mock dispatch fault')
        monkeypatch.setattr(campaigns.MockMailer, 'send', fail)
        with pytest.raises(RuntimeError, match='temporary'):
            campaigns.process_dispatch(db, obj.id)
        db.refresh(obj)
        assert obj.status == 'FAILED' and obj.failure_stage == 'dispatch'
        assert obj.dispatch_attempt == 1 and obj.attempt == 1
        monkeypatch.setattr(campaigns.MockMailer, 'send', original)
        retry = campaigns.retry_campaign(db, obj.id)
        assert retry.status == 'DISPATCH_QUEUED'
        assert campaigns.process_dispatch(db, obj.id)
        db.refresh(obj)
        assert obj.status == 'COMPLETED' and obj.dispatch_attempt == 2
        assert db.scalar(select(ContentVersion).where(ContentVersion.campaign_id == obj.id,
            ContentVersion.version_number == 2)) is None
        assert len(db.scalars(select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == obj.id)).all()) == 1
        assert len(db.scalars(select(ExecutionAttempt).where(
            ExecutionAttempt.campaign_id == obj.id, ExecutionAttempt.stage == 'dispatch')).all()) == 2


def test_expired_dispatch_lease_recovers_and_fences_old_token():
    with session_factory()() as db:
        obj = _new(db, 'expired-dispatch')
        claimed = campaigns._claim(db, obj.id, 'dispatch', ('APPROVED',))
        assert claimed is not None
        token, _ = claimed
        obj = db.get(Campaign, obj.id)
        obj.lease_until = utcnow() - timedelta(minutes=10)
        db.commit()
        assert campaigns.recover_stale(db) == 1
        db.refresh(obj)
        assert obj.status == 'DISPATCH_QUEUED' and obj.execution_token is None
        assert not campaigns.process_generation(db, obj.id)
        assert campaigns.process_dispatch(db, obj.id)
        assert obj.status == 'COMPLETED'
        previous = db.scalar(select(ExecutionAttempt).where(ExecutionAttempt.execution_token == token))
        assert previous.status == 'TIMED_OUT'


def test_unsubscribe_blocks_future_campaign_even_after_csv_reimport():
    with session_factory()() as db:
        obj = _new(db, 'unsub-first')
        campaigns.process_dispatch(db, obj.id)
        recipient = db.scalar(select(CampaignRecipient).where(CampaignRecipient.campaign_id == obj.id))
        assert record_demo_event(db, DemoEventIn(recipient_id=recipient.id,
            provider_event_id='delivered-unsub', event_type='delivered'))
        unsub = DemoEventIn(recipient_id=recipient.id, provider_event_id='unsub-unique',
                            event_type='unsubscribed')
        assert record_demo_event(db, unsub)
        assert not record_demo_event(db, unsub)
        contact = db.get(Contact, recipient.contact_id)
        assert contact.marketing_consent is False
        assert contact.suppression_reason == 'unsubscribed' and contact.suppressed_at
        campaigns.import_contacts(db, [ContactIn(email=contact.email, firstname='Alice',
            lastname='Demo', company='Fictional', persona_segment='ops_lead', marketing_consent=True)])
        db.refresh(contact)
        assert contact.marketing_consent is False
        second, _ = campaigns.create_campaign(db, CampaignCreate(topic='AI workflow optimization'), 'unsub-second')
        campaigns.process_generation(db, second.id)
        campaigns.approve_campaign(db, second.id)
        campaigns.process_dispatch(db, second.id)
        m = campaign_metrics(db, second.id)
        assert m['skipped_no_consent'] == 1 and m['simulated_send_count'] == 0
        assert m['by_persona']['ops_lead']['simulated_send_count'] == 0


def test_sql_persona_metrics_are_unique_and_do_not_invent_real_performance():
    with session_factory()() as db:
        obj = _new(db, 'persona-metrics')
        campaigns.process_dispatch(db, obj.id)
        recipient = db.scalar(select(CampaignRecipient).where(CampaignRecipient.campaign_id == obj.id))
        for kind, id in [('delivered', 'd1'), ('opened', 'o1'), ('opened', 'o2'),
                         ('clicked', 'c1')]:
            record_demo_event(db, DemoEventIn(recipient_id=recipient.id,
                provider_event_id=f'persona-{id}', event_type=kind))
        m = campaign_metrics(db, obj.id)
        assert m['delivered_count'] == 1 and m['unique_open_count'] == 1
        assert m['by_persona']['ops_lead']['open_rate'] == 1.0
        assert not m['is_real_world_performance']
