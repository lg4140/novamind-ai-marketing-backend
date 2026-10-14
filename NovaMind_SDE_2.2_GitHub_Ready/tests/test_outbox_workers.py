from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import OutboxEvent
from app.db.session import session_factory
from app.schemas import CampaignCreate
from app.services.campaigns import create_campaign, get_campaign
from app.workers import outbox, tasks


def _celery_mode(monkeypatch):
    monkeypatch.setenv('QUEUE_MODE', 'celery')
    get_settings.cache_clear()


def test_outbox_retries_then_publishes_without_losing_event(monkeypatch):
    _celery_mode(monkeypatch)
    with session_factory()() as db:
        c, _ = create_campaign(db, CampaignCreate(topic='AI workflow optimization'), 'outbox-1')
        event = db.scalar(select(OutboxEvent).where(OutboxEvent.payload['campaign_id'].as_string() == c.id))
        event_id = event.id
    def broken(*_):
        raise ConnectionError('broker unavailable')
    monkeypatch.setattr(outbox, 'send_task', broken)
    assert outbox.publish_pending() == 0
    with session_factory()() as db:
        pending = db.get(OutboxEvent, event_id)
        assert pending.status == 'PENDING' and pending.attempts == 1
        pending.next_attempt_at = None
        db.commit()
    observed = []
    monkeypatch.setattr(outbox, 'send_task', lambda *args: observed.append(args))
    assert outbox.publish_pending() == 1
    assert observed[0][0] == event_id
    assert outbox.publish_pending() == 0
    with session_factory()() as db:
        assert db.get(OutboxEvent, event_id).status == 'PUBLISHED'


def test_worker_consumer_handles_duplicate_generation(monkeypatch):
    with session_factory()() as db:
        c, _ = create_campaign(db, CampaignCreate(topic='Workflow for agencies'), 'worker-1')
        cid = c.id
    tasks.process_event('campaign.generate', cid)
    tasks.process_event('campaign.generate', cid)
    with session_factory()() as db:
        assert get_campaign(db, cid).status == 'REVIEW_REQUIRED'


def test_worker_rejects_unknown_event():
    import pytest
    with pytest.raises(ValueError, match='Unknown event'):
        tasks.process_event('not.supported', 'example')
