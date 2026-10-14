"""Connection lifecycle: SQLite for zero-credential demo; PostgreSQL supported."""
from functools import lru_cache
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.db.models import Base

@lru_cache
def engine():
    url = get_settings().database_url
    if url.startswith('sqlite:///') and ':memory:' not in url:
        Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
    db_engine = create_engine(url, pool_pre_ping=True,
                    connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
    if url.startswith('sqlite'):
        @event.listens_for(db_engine, 'connect')
        def _enable_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    return db_engine

@lru_cache
def session_factory():
    return sessionmaker(bind=engine(), expire_on_commit=False)

def init_database():
    if get_settings().database_auto_create:
        Base.metadata.create_all(engine())

def get_db():
    with session_factory()() as session:
        yield session
