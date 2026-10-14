import pytest
from app.core.config import get_settings
from app.db.session import engine, init_database, session_factory

@pytest.fixture(autouse=True)
def clean_database(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path / "test.db"}')
    monkeypatch.setenv('DATABASE_AUTO_CREATE','true')
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('QUEUE_MODE','inline')
    monkeypatch.setenv('AI_PROVIDER','mock')
    monkeypatch.setenv('CRM_PROVIDER','mock')
    monkeypatch.setenv('ALLOW_DEMO_EVENTS','true')
    get_settings.cache_clear()
    engine.cache_clear()
    session_factory.cache_clear()
    init_database()
    yield
    engine().dispose()
    session_factory.cache_clear()
    engine.cache_clear()
    get_settings.cache_clear()
