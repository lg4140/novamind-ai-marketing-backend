"""Validated, safe-by-default service configuration."""
from functools import lru_cache
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    app_env: Literal['development','test','production'] = 'development'
    database_url: str = 'sqlite:///./data/novamind.db'
    database_auto_create: bool = True
    api_token: str = 'dev-only-change-me'
    ai_provider: Literal['mock','openai'] = 'mock'
    openai_api_key: str | None = None
    openai_model: str = 'gpt-4.1-mini'
    crm_provider: Literal['mock','hubspot'] = 'mock'
    hubspot_access_token: str | None = None
    hubspot_base_url: str = 'https://api.hubapi.com'
    allow_live_crm_sync: bool = False
    queue_mode: Literal['inline','celery'] = 'inline'
    redis_url: str = 'redis://localhost:6379/0'
    allow_demo_events: bool = True
    lease_seconds: int = Field(default=300, ge=30, le=1800)

    @model_validator(mode='after')
    def verify_safety(self):
        if self.app_env == 'production':
            if self.api_token == 'dev-only-change-me' or len(self.api_token) < 24:
                raise ValueError('Production requires a strong API_TOKEN.')
            if self.database_auto_create:
                raise ValueError('Use Alembic migrations, not auto_create, in production.')
            if self.allow_demo_events:
                raise ValueError('Disable demo events in production.')
            if not self.database_url.startswith('postgresql'):
                raise ValueError('Production requires PostgreSQL; SQLite is demo only.')
        if self.ai_provider == 'openai' and not self.openai_api_key:
            raise ValueError('OPENAI_API_KEY is required with AI_PROVIDER=openai.')
        if self.crm_provider == 'hubspot' and (not self.allow_live_crm_sync or not self.hubspot_access_token):
            raise ValueError('HubSpot CRM sync requires explicit opt-in and a token.')
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
