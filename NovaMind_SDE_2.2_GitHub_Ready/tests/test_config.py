import pytest
from pydantic import ValidationError
from app.core.config import Settings

def test_production_guard():
    with pytest.raises(ValidationError):
        Settings(app_env='production',api_token='dev-only-change-me')
    with pytest.raises(ValidationError):
        Settings(ai_provider='openai',openai_api_key=None)
    with pytest.raises(ValidationError):
        Settings(crm_provider='hubspot',hubspot_access_token='fake',allow_live_crm_sync=False)
