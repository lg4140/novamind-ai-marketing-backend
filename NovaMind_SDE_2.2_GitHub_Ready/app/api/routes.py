"""Versioned HTTP endpoints. Auth for mutation AND contact/event reads."""
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.models import CampaignRecipient, Contact, ContentVersion, ExecutionAttempt
from app.db.session import get_db
from app.schemas import CampaignCreate, CampaignResponse, ContactIn, DemoEventIn
from app.integrations.hubspot import HubSpotCRM
from app.services.analytics import analyze_campaign, campaign_metrics, record_demo_event
from app.services.campaigns import (ConflictError, DomainError, approve_campaign,
    cancel_campaign, create_campaign, get_campaign, import_contacts,
    process_dispatch, process_generation, request_dispatch, request_revision, retry_campaign)

router = APIRouter(prefix='/api/v1', dependencies=[])
bearer = HTTPBearer(auto_error=False)

def authorized(credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    if credentials is None or not secrets.compare_digest(credentials.credentials, get_settings().api_token):
        raise HTTPException(status_code=401, detail='Valid bearer token required.')

@router.post('/contacts/import', dependencies=[Depends(authorized)])
def import_contact_list(items: list[ContactIn], db: Session = Depends(get_db)):
    return {'imported':import_contacts(db, items)}

@router.post('/contacts/sync-crm', dependencies=[Depends(authorized)])
def sync_crm(db: Session = Depends(get_db)):
    """Explicitly sync all contacts to CRM only when opted in; no email sending."""
    contacts = db.scalars(select(Contact).order_by(Contact.email)).all()
    payload = [{'email': c.email, 'firstname': c.firstname, 'lastname': c.lastname,
                'company': c.company, 'persona_segment': c.persona_segment}
               for c in contacts]
    try:
        return HubSpotCRM().upsert_contacts(payload)
    except Exception as exc:
        raise HTTPException(502, f'CRM sync failed: {type(exc).__name__}') from exc

@router.post('/campaigns', status_code=status.HTTP_202_ACCEPTED,
             response_model=CampaignResponse, dependencies=[Depends(authorized)])
def create_campaign_endpoint(request: CampaignCreate,
                             idempotency_key: str = Header(..., alias='Idempotency-Key'),
                             db: Session = Depends(get_db)):
    try:
        campaign, created = create_campaign(db, request, idempotency_key)
        if created and get_settings().queue_mode == 'inline':
            process_generation(db, campaign.id)
            db.refresh(campaign)
        return campaign
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.get('/campaigns/{campaign_id}', response_model=CampaignResponse,
            dependencies=[Depends(authorized)])
def read_campaign(campaign_id: str, db: Session = Depends(get_db)):
    try:
        return get_campaign(db, campaign_id)
    except DomainError as exc:
        raise HTTPException(404, str(exc)) from exc

@router.get('/campaigns/{campaign_id}/content', dependencies=[Depends(authorized)])
def read_content(campaign_id: str, db: Session = Depends(get_db)):
    obj = db.scalar(select(ContentVersion).where(ContentVersion.campaign_id == campaign_id)
                    .order_by(ContentVersion.version_number.desc()))
    if not obj:
        raise HTTPException(404, 'Content not generated.')
    return {'campaign_id':campaign_id, 'provider':obj.provider,
            'prompt_version':obj.prompt_version,'content':obj.payload}

@router.post('/campaigns/{campaign_id}/approve', response_model=CampaignResponse,
             dependencies=[Depends(authorized)])
def approve(campaign_id: str, db: Session = Depends(get_db)):
    try:
        return approve_campaign(db, campaign_id)
    except DomainError as exc:
        raise HTTPException(409 if isinstance(exc, ConflictError) else 404, str(exc)) from exc

@router.post('/campaigns/{campaign_id}/revise', response_model=CampaignResponse,
             dependencies=[Depends(authorized)])
def revise(campaign_id: str, db: Session = Depends(get_db)):
    try:
        obj = request_revision(db, campaign_id)
        if get_settings().queue_mode == 'inline':
            process_generation(db, campaign_id)
            db.refresh(obj)
        return obj
    except DomainError as exc:
        raise HTTPException(409 if isinstance(exc, ConflictError) else 404, str(exc)) from exc

@router.post('/campaigns/{campaign_id}/dispatch', response_model=CampaignResponse,
             dependencies=[Depends(authorized)])
def dispatch(campaign_id: str, db: Session = Depends(get_db)):
    try:
        campaign = request_dispatch(db, campaign_id)
        if get_settings().queue_mode == 'inline':
            process_dispatch(db, campaign_id)
            db.refresh(campaign)
        return campaign
    except DomainError as exc:
        raise HTTPException(409 if isinstance(exc, ConflictError) else 404, str(exc)) from exc

@router.post('/campaigns/{campaign_id}/retry', response_model=CampaignResponse,
             dependencies=[Depends(authorized)])
def retry(campaign_id: str, db: Session = Depends(get_db)):
    try:
        c = retry_campaign(db, campaign_id)
        if get_settings().queue_mode == 'inline':
            if c.status == 'QUEUED':
                process_generation(db, campaign_id)
            elif c.status == 'DISPATCH_QUEUED':
                process_dispatch(db, campaign_id)
            db.refresh(c)
        return c
    except DomainError as exc:
        raise HTTPException(409 if isinstance(exc, ConflictError) else 404, str(exc)) from exc

@router.post('/campaigns/{campaign_id}/cancel', response_model=CampaignResponse,
             dependencies=[Depends(authorized)])
def cancel(campaign_id: str, db: Session = Depends(get_db)):
    try:
        return cancel_campaign(db, campaign_id)
    except DomainError as exc:
        raise HTTPException(409 if isinstance(exc, ConflictError) else 404, str(exc)) from exc

@router.get('/campaigns/{campaign_id}/executions', dependencies=[Depends(authorized)])
def execution_history(campaign_id: str, db: Session = Depends(get_db)):
    try:
        get_campaign(db, campaign_id)
    except DomainError as exc:
        raise HTTPException(404, str(exc)) from exc
    rows = db.scalars(select(ExecutionAttempt).where(
        ExecutionAttempt.campaign_id == campaign_id)
        .order_by(ExecutionAttempt.started_at, ExecutionAttempt.id).limit(100)).all()
    return [{'stage': r.stage, 'attempt_number': r.attempt_number,
             'status': r.status, 'error_category': r.error_category,
             'started_at': r.started_at, 'finished_at': r.finished_at}
            for r in rows]

@router.get('/campaigns/{campaign_id}/recipients', dependencies=[Depends(authorized)])
def recipients(campaign_id: str, db: Session = Depends(get_db)):
    try:
        get_campaign(db, campaign_id)
    except DomainError as exc:
        raise HTTPException(404, str(exc)) from exc
    records = db.scalars(select(CampaignRecipient).where(
        CampaignRecipient.campaign_id == campaign_id)).all()
    return [{'id':r.id,'status':r.status,'subject':r.newsletter_subject,
             'persona_at_dispatch':r.persona_at_dispatch,
             'content_version_id':r.content_version_id,
             'snapshot_source':r.snapshot_source} for r in records]

@router.get('/campaigns/{campaign_id}/metrics', dependencies=[Depends(authorized)])
def metrics(campaign_id: str, db: Session = Depends(get_db)):
    try:
        return campaign_metrics(db, campaign_id)
    except DomainError as exc:
        raise HTTPException(404, str(exc)) from exc

@router.post('/campaigns/{campaign_id}/analysis', dependencies=[Depends(authorized)])
def analysis(campaign_id: str, db: Session = Depends(get_db)):
    try:
        return analyze_campaign(db, campaign_id)
    except DomainError as exc:
        raise HTTPException(404, str(exc)) from exc

@router.post('/events/demo', dependencies=[Depends(authorized)])
def demo_events(event: DemoEventIn, db: Session = Depends(get_db)):
    if not get_settings().allow_demo_events:
        raise HTTPException(403, 'Synthetic event endpoint is disabled.')
    try:
        return {'created':record_demo_event(db, event)}
    except DomainError as exc:
        raise HTTPException(422, str(exc)) from exc
