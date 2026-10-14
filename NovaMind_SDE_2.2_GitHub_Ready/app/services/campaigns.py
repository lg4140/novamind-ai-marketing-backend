"""Campaign lifecycle and guarded execution. Only the mock mailer is supported."""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.models import (
    Campaign, CampaignRecipient, Contact, ContentVersion, ExecutionAttempt, OutboxEvent, utcnow,
)
from app.integrations.ai import generate_content
from app.integrations.hubspot import MockMailer
from app.schemas import CampaignCreate, ContactIn

MAX_ATTEMPTS = 3


class DomainError(ValueError):
    pass


class ConflictError(DomainError):
    pass


def get_campaign(db: Session, campaign_id: str) -> Campaign:
    obj = db.get(Campaign, campaign_id)
    if obj is None:
        raise DomainError('Campaign not found.')
    return obj


def _event(db: Session, name: str, campaign_id: str) -> None:
    if get_settings().queue_mode == 'celery':
        db.add(OutboxEvent(event_type=name, payload={'campaign_id': campaign_id}))


def create_campaign(db: Session, request: CampaignCreate, idem_key: str) -> tuple[Campaign, bool]:
    key = idem_key.strip()
    if not 1 <= len(key) <= 128:
        raise DomainError('Idempotency-Key header must be 1-128 characters.')
    personas = list(dict.fromkeys(request.personas))
    existing = db.scalar(select(Campaign).where(Campaign.idempotency_key == key))
    if existing is not None:
        if existing.topic != request.topic or existing.personas != personas:
            raise ConflictError('Idempotency-Key already used for different input.')
        return existing, False
    obj = Campaign(idempotency_key=key, topic=request.topic, personas=personas)
    db.add(obj)
    try:
        db.flush()
        _event(db, 'campaign.generate', obj.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(select(Campaign).where(Campaign.idempotency_key == key))
        if existing and existing.topic == request.topic and existing.personas == personas:
            return existing, False
        raise ConflictError('Concurrent idempotency-key collision.') from exc
    return obj, True


def import_contacts(db: Session, items: list[ContactIn]) -> int:
    for item in items:
        email = item.email.casefold().strip()
        existing = db.scalar(select(Contact).where(Contact.email == email))
        if existing is None:
            db.add(Contact(email=email, firstname=item.firstname, lastname=item.lastname,
                           company=item.company, persona_segment=item.persona_segment,
                           marketing_consent=item.marketing_consent))
        else:
            existing.firstname = item.firstname
            existing.lastname = item.lastname
            existing.company = item.company
            existing.persona_segment = item.persona_segment
            # Neither CSV import nor later synthetic opt-in should lift a suppression.
            existing.marketing_consent = (existing.marketing_consent and item.marketing_consent
                                          and existing.suppression_reason is None)
    db.commit()
    return len(items)


def _claim(db: Session, campaign_id: str, stage: str, sources: tuple[str, ...]) -> tuple[str, int] | None:
    token = str(uuid4())
    counter = Campaign.generation_retry_count if stage == 'generation' else Campaign.dispatch_attempt
    updates = {
        'status': 'GENERATING' if stage == 'generation' else 'DISPATCHING',
        'lease_until': utcnow() + timedelta(seconds=get_settings().lease_seconds),
        'execution_token': token,
        'failure_stage': None,
        'last_error': None,
    }
    if stage == 'generation':
        updates['attempt'] = Campaign.attempt + 1
        updates['generation_retry_count'] = counter + 1
    else:
        updates['dispatch_attempt'] = counter + 1
    changed = db.execute(update(Campaign).where(Campaign.id == campaign_id,
                    Campaign.status.in_(sources), counter < MAX_ATTEMPTS).values(**updates))
    if changed.rowcount != 1:
        db.rollback()
        return None
    obj = get_campaign(db, campaign_id)
    attempt = obj.attempt if stage == 'generation' else obj.dispatch_attempt
    db.add(ExecutionAttempt(campaign_id=campaign_id, stage=stage, attempt_number=attempt,
                            execution_token=token, status='RUNNING'))
    db.commit()
    return token, attempt


def renew_execution_lease(db: Session, campaign_id: str, token: str, stage: str) -> bool:
    """CAS heartbeat; never revive a superseded or terminal execution."""
    if stage not in {'generation', 'dispatch'}:
        raise DomainError('Unknown execution stage.')
    state = 'GENERATING' if stage == 'generation' else 'DISPATCHING'
    result = db.execute(update(Campaign).where(
        Campaign.id == campaign_id, Campaign.status == state,
        Campaign.execution_token == token).values(
        lease_until=utcnow() + timedelta(seconds=get_settings().lease_seconds)))
    db.commit()
    return result.rowcount == 1


def _mark_execution(db: Session, campaign_id: str, token: str,
                    stage: str, outcome: str, error: str | None = None) -> None:
    execution = db.scalar(select(ExecutionAttempt).where(
        ExecutionAttempt.campaign_id == campaign_id,
        ExecutionAttempt.execution_token == token,
        ExecutionAttempt.stage == stage))
    if execution:
        execution.status = outcome
        execution.finished_at = utcnow()
        execution.error_category = error


def _fail(db: Session, campaign_id: str, token: str, stage: str, exc: Exception) -> None:
    db.rollback()
    status = 'GENERATING' if stage == 'generation' else 'DISPATCHING'
    changed = db.execute(update(Campaign).where(Campaign.id == campaign_id,
        Campaign.status == status, Campaign.execution_token == token).values(
        status='FAILED', failure_stage=stage, execution_token=None, lease_until=None,
        last_error=f'{type(exc).__name__}: {stage} did not complete'))
    if changed.rowcount:
        _mark_execution(db, campaign_id, token, stage, 'FAILED', type(exc).__name__)
        db.commit()
    else:
        db.rollback()


def process_generation(db: Session, campaign_id: str) -> bool:
    claim = _claim(db, campaign_id, 'generation', ('QUEUED',))
    if claim is None:
        return False
    token, _ = claim
    try:
        topic = get_campaign(db, campaign_id).topic
        # Release read transactions before the external call so the heartbeat
        # can write its renewal using an independent connection.
        db.rollback()
        from app.workers.leases import generation_heartbeat
        with generation_heartbeat(campaign_id, token):
            content, provider = generate_content(topic)
        # DB compare-and-swap fences off stale workers after lease recovery.
        changed = db.execute(update(Campaign).where(
            Campaign.id == campaign_id, Campaign.status == 'GENERATING',
            Campaign.execution_token == token).values(
            status='REVIEW_REQUIRED', execution_token=None, lease_until=None))
        if changed.rowcount != 1:
            db.rollback()
            return False
        latest = db.scalar(select(func.max(ContentVersion.version_number)).where(
            ContentVersion.campaign_id == campaign_id)) or 0
        db.add(ContentVersion(campaign_id=campaign_id, version_number=latest + 1,
                              prompt_version='content-v2.1', provider=provider,
                              payload=content.model_dump(mode='json')))
        _mark_execution(db, campaign_id, token, 'generation', 'SUCCEEDED')
        db.commit()
    except Exception as exc:
        _fail(db, campaign_id, token, 'generation', exc)
        raise
    return True


def approve_campaign(db: Session, campaign_id: str) -> Campaign:
    obj = get_campaign(db, campaign_id)
    current = db.scalar(select(func.max(ContentVersion.version_number)).where(
        ContentVersion.campaign_id == campaign_id))
    if current is None:
        raise ConflictError('Cannot approve without generated content.')
    changed = db.execute(update(Campaign).where(
        Campaign.id == campaign_id, Campaign.status == 'REVIEW_REQUIRED').values(
        status='APPROVED', approved_version_number=current))
    if changed.rowcount != 1:
        db.rollback()
        raise ConflictError('Only campaigns awaiting review can be approved.')
    db.commit()
    db.refresh(obj)
    return obj


def request_revision(db: Session, campaign_id: str) -> Campaign:
    """Request a fresh content version; a new human approval is mandatory."""
    obj = get_campaign(db, campaign_id)
    changed = db.execute(update(Campaign).where(
        Campaign.id == campaign_id,
        Campaign.status.in_(['REVIEW_REQUIRED', 'APPROVED']),
        Campaign.content_revision_count < 100).values(
        status='QUEUED', approved_version_number=None, last_error=None,
        generation_retry_count=0, content_revision_count=Campaign.content_revision_count + 1))
    if changed.rowcount != 1:
        db.rollback()
        raise ConflictError('Revision requires review/approval state and available version budget.')
    _event(db, 'campaign.generate', campaign_id)
    db.commit()
    db.refresh(obj)
    return obj


def request_dispatch(db: Session, campaign_id: str) -> Campaign:
    obj = get_campaign(db, campaign_id)
    if get_settings().queue_mode == 'celery':
        changed = db.execute(update(Campaign).where(Campaign.id == campaign_id,
            Campaign.status == 'APPROVED').values(status='DISPATCH_QUEUED'))
        if changed.rowcount != 1:
            db.rollback()
            raise ConflictError('Campaign must be approved before dispatch.')
        _event(db, 'campaign.dispatch', campaign_id)
        db.commit()
        db.refresh(obj)
    elif obj.status != 'APPROVED':
        raise ConflictError('Campaign must be approved before dispatch.')
    return obj


def process_dispatch(db: Session, campaign_id: str) -> bool:
    claim = _claim(db, campaign_id, 'dispatch', ('APPROVED', 'DISPATCH_QUEUED'))
    if claim is None:
        return False
    token, _ = claim
    try:
        campaign = get_campaign(db, campaign_id)
        version = db.scalar(select(ContentVersion).where(
            ContentVersion.campaign_id == campaign_id,
            ContentVersion.version_number == campaign.approved_version_number))
        if version is None:
            raise DomainError('Missing approved content version.')
        contacts = db.scalars(select(Contact).where(Contact.persona_segment.in_(campaign.personas))
                              .order_by(Contact.email)).all()
        mock = MockMailer()
        for contact in contacts:
            newsletter = version.payload['newsletters'][contact.persona_segment]
            status = (mock.send({'email': contact.email}, newsletter)
                      if contact.marketing_consent and not contact.suppression_reason
                      else 'SKIPPED_NO_CONSENT')
            # Mock-only; a real provider requires persisted send intents BEFORE any side effect.
            exists = db.scalar(select(CampaignRecipient.id).where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.contact_id == contact.id))
            if exists is None:
                db.add(CampaignRecipient(campaign_id=campaign_id, contact_id=contact.id,
                    status=status, newsletter_subject=newsletter['subject'],
                    persona_at_dispatch=contact.persona_segment, content_version_id=version.id,
                    consent_at_dispatch=bool(contact.marketing_consent and not contact.suppression_reason),
                    snapshot_source='captured_at_dispatch', dispatched_at=utcnow()))
        changed = db.execute(update(Campaign).where(
            Campaign.id == campaign_id, Campaign.status == 'DISPATCHING',
            Campaign.execution_token == token).values(
            status='COMPLETED', execution_token=None, lease_until=None))
        if changed.rowcount != 1:
            db.rollback()
            return False
        _mark_execution(db, campaign_id, token, 'dispatch', 'SUCCEEDED')
        db.commit()
    except Exception as exc:
        _fail(db, campaign_id, token, 'dispatch', exc)
        raise
    return True


def cancel_campaign(db: Session, campaign_id: str) -> Campaign:
    obj = get_campaign(db, campaign_id)
    changed = db.execute(update(Campaign).where(Campaign.id == campaign_id,
        Campaign.status.in_(['QUEUED', 'REVIEW_REQUIRED', 'APPROVED', 'FAILED'])).values(
        status='CANCELLED'))
    if changed.rowcount != 1:
        db.rollback()
        raise ConflictError('Campaign cannot be cancelled in the current state.')
    db.commit()
    db.refresh(obj)
    return obj


def retry_campaign(db: Session, campaign_id: str) -> Campaign:
    obj = get_campaign(db, campaign_id)
    if obj.status != 'FAILED' or obj.failure_stage not in {'generation', 'dispatch'}:
        raise ConflictError('Only campaigns with a classified failure may retry.')
    stage = obj.failure_stage
    count = obj.generation_retry_count if stage == 'generation' else obj.dispatch_attempt
    if count >= MAX_ATTEMPTS:
        raise ConflictError('Maximum attempts exhausted.')
    target = 'QUEUED' if stage == 'generation' else 'DISPATCH_QUEUED'
    changed = db.execute(update(Campaign).where(Campaign.id == campaign_id,
        Campaign.status == 'FAILED', Campaign.failure_stage == stage).values(
        status=target, last_error=None, failure_stage=None, lease_until=None))
    if changed.rowcount != 1:
        db.rollback()
        raise ConflictError('Concurrent retry conflict.')
    _event(db, 'campaign.generate' if stage == 'generation' else 'campaign.dispatch', campaign_id)
    db.commit()
    db.refresh(obj)
    return obj


def recover_stale(db: Session) -> int:
    """Manual recovery of expired mock-only stages; no ambiguous live sends exist."""
    stale = db.scalars(select(Campaign).where(
        Campaign.status.in_(['GENERATING', 'DISPATCHING']),
        Campaign.lease_until < utcnow())).all()
    recovered = 0
    for obj in stale:
        stage = 'generation' if obj.status == 'GENERATING' else 'dispatch'
        counter = obj.generation_retry_count if stage == 'generation' else obj.dispatch_attempt
        target = ('FAILED' if counter >= MAX_ATTEMPTS
                  else ('QUEUED' if stage == 'generation' else 'DISPATCH_QUEUED'))
        previous_token = obj.execution_token
        changed = db.execute(update(Campaign).where(
            Campaign.id == obj.id, Campaign.status == obj.status,
            Campaign.execution_token == previous_token,
            Campaign.lease_until < utcnow()).values(
            status=target, execution_token=None, lease_until=None,
            failure_stage=stage if target == 'FAILED' else None,
            last_error='Execution lease expired; prior attempt is fenced off.'))
        if changed.rowcount != 1:
            continue
        if previous_token:
            _mark_execution(db, obj.id, previous_token, stage, 'TIMED_OUT', 'LeaseExpired')
        if target != 'FAILED':
            _event(db, 'campaign.generate' if stage == 'generation' else 'campaign.dispatch', obj.id)
        recovered += 1
    db.commit()
    return recovered
