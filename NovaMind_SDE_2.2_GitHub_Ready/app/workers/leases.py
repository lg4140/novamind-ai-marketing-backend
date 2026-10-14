"""Best-effort heartbeat for remote content-generation calls in PostgreSQL/Celery mode.

The campaign's opaque token remains the authoritative fencing guard. Missing
heartbeats can cause safe duplicate AI work; they never authorize live emails.
"""
import logging
from contextlib import contextmanager
from threading import Event, Thread
from app.core.config import get_settings
from app.db.session import session_factory

logger = logging.getLogger(__name__)


@contextmanager
def generation_heartbeat(campaign_id: str, token: str):
    settings = get_settings()
    # Inline/SQLite fixtures deliberately avoid background connection contention.
    if settings.queue_mode != 'celery' or not settings.database_url.startswith('postgresql'):
        yield
        return

    stopper = Event()
    interval = max(5, settings.lease_seconds // 3)

    def beat():
        from app.services.campaigns import renew_execution_lease
        while not stopper.wait(interval):
            try:
                with session_factory()() as db:
                    if not renew_execution_lease(db, campaign_id, token, 'generation'):
                        return
            except Exception as exc:
                logger.warning('generation heartbeat failed campaign_id=%s type=%s',
                               campaign_id, type(exc).__name__)

    worker = Thread(target=beat, name='novamind-lease-heartbeat', daemon=True)
    worker.start()
    try:
        yield
    finally:
        stopper.set()
        worker.join(timeout=5)
