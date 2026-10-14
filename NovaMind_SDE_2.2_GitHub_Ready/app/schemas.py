"""Validated transport contracts and OpenAI structured-output shape."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Persona = Literal['ops_lead','creative_director','freelancer']
PERSONAS = ('ops_lead','creative_director','freelancer')

class Newsletter(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    preview_text: str = Field(min_length=3)
    body: str = Field(min_length=20)
    cta_text: str = Field(min_length=2)

class NewsletterSet(BaseModel):
    ops_lead: Newsletter
    creative_director: Newsletter
    freelancer: Newsletter

class GeneratedContent(BaseModel):
    topic: str
    blog_title: str
    blog_outline: list[str] = Field(min_length=3)
    blog_draft: str = Field(min_length=100)
    newsletters: NewsletterSet

class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic: str = Field(min_length=5, max_length=250)
    personas: list[Persona] = Field(default_factory=lambda: list(PERSONAS), min_length=1)

class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    topic: str
    personas: list[str]
    status: str
    attempt: int
    generation_retry_count: int
    content_revision_count: int
    dispatch_attempt: int
    failure_stage: str | None
    approved_version_number: int | None
    last_error: str | None

class ContactIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=6, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    firstname: str = Field(min_length=1)
    lastname: str = Field(min_length=1)
    company: str = Field(min_length=1)
    persona_segment: Persona
    marketing_consent: bool = False

class DemoEventIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recipient_id: str
    provider_event_id: str = Field(min_length=4, max_length=180)
    event_type: Literal['delivered','opened','clicked','unsubscribed']
