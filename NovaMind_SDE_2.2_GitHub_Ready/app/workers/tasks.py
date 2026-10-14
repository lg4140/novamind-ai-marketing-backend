"""At-least-once worker consumers; compare-and-swap guards transitions."""
from app.core.config import get_settings
from app.db.session import init_database, session_factory

try:
    from celery import Celery
except ImportError:  # local core tests can run without optional broker runtime
    Celery = None

if Celery is not None:
    celery_app = Celery('novamind', broker=get_settings().redis_url)
    celery_app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1,
                           task_track_started=True, task_serializer='json',
                           accept_content=['json'], worker_max_tasks_per_child=500)
else:
    celery_app = None


def process_event(event_type: str, campaign_id: str) -> None:
    from app.services.campaigns import process_dispatch, process_generation
    init_database()
    with session_factory()() as db:
        if event_type == 'campaign.generate':
            process_generation(db, campaign_id)
        elif event_type == 'campaign.dispatch':
            process_dispatch(db, campaign_id)
        else:
            raise ValueError(f'Unknown event: {event_type}')


if celery_app is not None:
    @celery_app.task(name='novamind.process_event', acks_late=True)
    def celery_process_event(event_type: str, campaign_id: str):
        process_event(event_type, campaign_id)
else:
    def celery_process_event(*_args, **_kwargs):
        raise RuntimeError('Celery dependency is required to publish broker tasks.')
