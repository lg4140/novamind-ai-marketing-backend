from datetime import timedelta
import pytest
from app.db.session import session_factory
from app.db.models import utcnow
from app.schemas import CampaignCreate, ContactIn
from app.services.campaigns import (create_campaign, import_contacts, process_generation,
                                    recover_stale, retry_campaign)


def test_consent_downgrade_is_sticky():
    with session_factory()() as db:
        c=ContactIn(email='x@example.test',firstname='One',lastname='Two',
                    company='C',persona_segment='freelancer',marketing_consent=True)
        import_contacts(db,[c])
        import_contacts(db,[c.model_copy(update={'marketing_consent':False})])
        import_contacts(db,[c])
        from sqlalchemy import select
        from app.db.models import Contact
        assert db.scalar(select(Contact).where(Contact.email=='x@example.test')).marketing_consent is False


def test_failed_generation_manual_retry(monkeypatch):
    with session_factory()() as db:
        c,_=create_campaign(db,CampaignCreate(topic='AI creative optimization'),'broken-1')
        def fail(_topic):
            raise RuntimeError('temporary fake failure')
        from app.services import campaigns
        original=campaigns.generate_content
        monkeypatch.setattr(campaigns,'generate_content',fail)
        with pytest.raises(RuntimeError):
            process_generation(db,c.id)
        db.refresh(c)
        assert c.status=='FAILED' and 'RuntimeError' in c.last_error
        monkeypatch.setattr(campaigns,'generate_content',original)
        retry_campaign(db,c.id)
        assert process_generation(db,c.id)
        db.refresh(c)
        assert c.status=='REVIEW_REQUIRED' and c.attempt==2


def test_expired_lease_recovery():
    with session_factory()() as db:
        c,_=create_campaign(db,CampaignCreate(topic='AI creative workflows'),'lease-1')
        c.status='GENERATING'
        c.attempt=1
        c.lease_until=utcnow()-timedelta(minutes=10)
        db.commit()
        assert recover_stale(db)==1
        db.refresh(c)
        assert c.status=='QUEUED' and c.lease_until is None
