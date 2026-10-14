"""Leased transactional outbox (at-least-once broker publication).

Claiming and publishing are intentionally separate transactions. A crash after
broker acknowledgement but before DB acknowledgement may republish the message;
consumer state fencing is mandatory. PostgreSQL SKIP LOCKED enables several
publishers. SQLite remains a one-process development demonstration.
"""
import logging
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from app.core.config import get_settings
from app.db.models import OutboxEvent, utcnow
from app.db.session import session_factory

logger = logging.getLogger(__name__)
MAX_PUBLISH_ATTEMPTS = 5
OUTBOX_LEASE_SECONDS = 300


def send_task(event_id: str, event_type: str, campaign_id: str) -> None:
    from app.workers.tasks import celery_process_event
    celery_process_event.apply_async(args=(event_type, campaign_id), task_id=event_id)


def claim_pending(limit: int = 50) -> list[tuple[str, str]]:
    """Atomically take a renewable batch; commit claims BEFORE network I/O."""
    limit = max(0, min(limit, 100))
    if not limit:
        return []
    now = utcnow()
    available = or_(
        and_(OutboxEvent.status == 'PENDING',
             or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now)),
        and_(OutboxEvent.status == 'PUBLISHING', OutboxEvent.lease_until < now),
    )
    claimed = []
    with session_factory()() as db:
        q = (select(OutboxEvent.id).where(available)
             .order_by(OutboxEvent.created_at, OutboxEvent.id).limit(limit))
        if db.bind.dialect.name == 'postgresql':
            q = q.with_for_update(skip_locked=True)
        for event_id in db.scalars(q).all():
            token = str(uuid4())
            updated = db.execute(update(OutboxEvent).where(
                OutboxEvent.id == event_id, available).values(
                status='PUBLISHING', lease_owner=token,
                lease_until=now + timedelta(seconds=OUTBOX_LEASE_SECONDS)))
            if updated.rowcount == 1:
                claimed.append((event_id, token))
        db.commit()
    return claimed


def _ack(event_id: str, token: str, error: Exception | None) -> bool:
    """Fencing token prevents an expired publisher from modifying newer claims."""
    with session_factory()() as db:
        row = db.scalar(select(OutboxEvent).where(
            OutboxEvent.id == event_id, OutboxEvent.status == 'PUBLISHING',
            OutboxEvent.lease_owner == token).with_for_update())
        if row is None:
            return False
        row.attempts += 1
        row.lease_owner = None
        row.lease_until = None
        if error is None:
            row.status = 'PUBLISHED'
            row.last_error = None
            row.next_attempt_at = None
            row.published_at = utcnow()
        else:
            row.last_error = type(error).__name__
            if row.attempts >= MAX_PUBLISH_ATTEMPTS:
                row.status = 'FAILED'
                row.next_attempt_at = None
            else:
                row.status = 'PENDING'
                row.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2 ** row.attempts))
            logger.warning('outbox publish failed event_id=%s attempt=%s type=%s',
                           row.id, row.attempts, type(error).__name__)
        db.commit()
        return True


def publish_pending(limit: int = 50) -> int:
    if get_settings().queue_mode != 'celery':
        raise RuntimeError('Outbox publisher only runs in celery mode.')
    claimed = claim_pending(limit)
    successful = 0
    for event_id, token in claimed:
        with session_factory()() as db:
            row = db.get(OutboxEvent, event_id)
            if row is None or row.lease_owner != token or row.status != 'PUBLISHING':
                continue
            event_type = row.event_type
            campaign_id = row.payload['campaign_id']
        try:
            send_task(event_id, event_type, campaign_id)
        except Exception as exc:
            _ack(event_id, token, exc)
        else:
            if _ack(event_id, token, None):
                successful += 1
    return successful
