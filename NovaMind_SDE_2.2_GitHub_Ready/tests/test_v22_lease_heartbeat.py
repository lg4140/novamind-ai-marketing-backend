"""Deterministic thread-level heartbeat unit test (not PostgreSQL evidence)."""
from contextlib import nullcontext
from threading import Event as RealEvent
from types import SimpleNamespace
from app.workers import leases
from app.services import campaigns


def test_generation_heartbeat_renews_using_separate_session(monkeypatch):
    called = RealEvent()
    monkeypatch.setattr(leases, 'get_settings', lambda: SimpleNamespace(
        queue_mode='celery', database_url='postgresql+psycopg://test/test', lease_seconds=30))
    monkeypatch.setattr(leases, 'session_factory', lambda: lambda: nullcontext(object()))

    class ImmediateWait:
        def __init__(self):
            self._stop = False
        def wait(self, _interval):
            return self._stop
        def set(self):
            self._stop = True

    monkeypatch.setattr(leases, 'Event', ImmediateWait)

    def renew(_db, campaign_id, token, stage):
        assert campaign_id == 'c-1' and token == 't-1' and stage == 'generation'
        called.set()
        return False
    monkeypatch.setattr(campaigns, 'renew_execution_lease', renew)

    with leases.generation_heartbeat('c-1', 't-1'):
        assert called.wait(timeout=1)
