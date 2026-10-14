"""Persistent domain entities. Mock delivery is not evidence of real delivery."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Campaign(Base):
    __tablename__ = 'campaigns'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    topic: Mapped[str] = mapped_column(String(250), nullable=False)
    personas: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='QUEUED', nullable=False, index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    failure_stage: Mapped[str | None] = mapped_column(String(24))
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # lifetime execution ordinal
    generation_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_revision_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dispatch_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_version_number: Mapped[int | None] = mapped_column(Integer)
    execution_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    content_versions: Mapped[list['ContentVersion']] = relationship(back_populates='campaign',
        order_by='ContentVersion.version_number', lazy='selectin')

    @property
    def content(self) -> 'ContentVersion | None':
        """Backward-compatible view of the most recent content revision."""
        return self.content_versions[-1] if self.content_versions else None


class ContentVersion(Base):
    __tablename__ = 'content_versions'
    __table_args__ = (UniqueConstraint('campaign_id', 'version_number', name='uq_content_campaign_version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey('campaigns.id'), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    campaign: Mapped[Campaign] = relationship(back_populates='content_versions')


class Contact(Base):
    __tablename__ = 'contacts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    firstname: Mapped[str] = mapped_column(String(120), nullable=False)
    lastname: Mapped[str] = mapped_column(String(120), nullable=False)
    company: Mapped[str] = mapped_column(String(180), nullable=False)
    persona_segment: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suppression_reason: Mapped[str | None] = mapped_column(String(64))
    suppressed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CampaignRecipient(Base):
    __tablename__ = 'campaign_recipients'
    __table_args__ = (
        UniqueConstraint('campaign_id', 'contact_id', name='uq_campaign_contact'),
        Index('ix_campaign_recipients_persona_snapshot', 'campaign_id', 'persona_at_dispatch'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey('campaigns.id'), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey('contacts.id'), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    newsletter_subject: Mapped[str] = mapped_column(String(250), nullable=False)
    persona_at_dispatch: Mapped[str] = mapped_column(String(50), nullable=False)
    content_version_id: Mapped[str | None] = mapped_column(ForeignKey('content_versions.id', name='fk_recipients_content_version'))
    consent_at_dispatch: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    snapshot_source: Mapped[str] = mapped_column(String(40), nullable=False, default='captured_at_dispatch')
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeliveryEvent(Base):
    __tablename__ = 'delivery_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_event_id: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    recipient_id: Mapped[str] = mapped_column(ForeignKey('campaign_recipients.id'), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    __tablename__ = 'outbox_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='PENDING', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(200))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PerformanceSummary(Base):
    __tablename__ = 'performance_summaries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey('campaigns.id'), nullable=False, index=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExecutionAttempt(Base):
    __tablename__ = 'execution_attempts'
    __table_args__ = (UniqueConstraint('campaign_id', 'stage', 'attempt_number', name='uq_execution_attempt'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey('campaigns.id'), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_token: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
