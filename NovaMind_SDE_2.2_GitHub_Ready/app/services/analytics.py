"""Synthetic-event analytics with durable suppression and persona breakdowns."""
from sqlalchemy import case, distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import Campaign, CampaignRecipient, Contact, DeliveryEvent, PerformanceSummary, utcnow
from app.schemas import DemoEventIn
from app.services.campaigns import DomainError

EVENTS = {'delivered', 'opened', 'clicked', 'unsubscribed'}


def record_demo_event(db: Session, event: DemoEventIn) -> bool:
    recipient = db.get(CampaignRecipient, event.recipient_id)
    if recipient is None or recipient.status != 'SIMULATED':
        raise DomainError('Demo event must reference a simulated recipient.')
    if event.event_type not in EVENTS:
        raise DomainError('Unsupported event.')
    # Events may arrive out of order. In particular, unsubscribe must never
    # depend on another provider event arriving first. Rates stay null without delivery.
    existing = db.scalar(select(DeliveryEvent).where(
        DeliveryEvent.provider_event_id == event.provider_event_id))
    if existing is not None:
        if existing.recipient_id == recipient.id and existing.event_type == event.event_type:
            return False
        raise DomainError('Event ID reused with different content.')
    db.add(DeliveryEvent(provider_event_id=event.provider_event_id, recipient_id=recipient.id,
                         event_type=event.event_type, source='synthetic_demo'))
    if event.event_type == 'unsubscribed':
        contact = db.get(Contact, recipient.contact_id)
        if contact:
            contact.marketing_consent = False
            contact.suppression_reason = 'unsubscribed'
            contact.suppressed_at = utcnow()
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        stored = db.scalar(select(DeliveryEvent).where(
            DeliveryEvent.provider_event_id == event.provider_event_id))
        if stored and stored.recipient_id == recipient.id and stored.event_type == event.event_type:
            return False
        raise DomainError('Event ID reused with different content.')


def campaign_metrics(db: Session, campaign_id: str) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise DomainError('Campaign not found.')

    def events_of(kind: str):
        return func.count(distinct(case((DeliveryEvent.event_type == kind, CampaignRecipient.id))))

    stmt = (select(CampaignRecipient.persona_at_dispatch,
          func.count(distinct(CampaignRecipient.id)).label('recipients'),
          func.count(distinct(case((CampaignRecipient.status == 'SIMULATED', CampaignRecipient.id)))).label('sends'),
          func.count(distinct(case((CampaignRecipient.status == 'SKIPPED_NO_CONSENT', CampaignRecipient.id)))).label('skipped'),
          events_of('delivered').label('delivered'), events_of('opened').label('opened'),
          events_of('clicked').label('clicked'), events_of('unsubscribed').label('unsubscribed'))
          .select_from(CampaignRecipient)
          .outerjoin(DeliveryEvent, DeliveryEvent.recipient_id == CampaignRecipient.id)
          .where(CampaignRecipient.campaign_id == campaign_id)
          .group_by(CampaignRecipient.persona_at_dispatch))
    rows = db.execute(stmt).all()
    breakdown = {}
    for r in rows:
        breakdown[r.persona_at_dispatch] = {
            'recipient_count': r.recipients,
            'simulated_send_count': r.sends,
            'skipped_no_consent': r.skipped,
            'delivered_count': r.delivered,
            'unique_open_count': r.opened,
            'unique_click_count': r.clicked,
            'unsubscribe_count': r.unsubscribed,
            'open_rate': round(r.opened / r.delivered, 4) if r.delivered else None,
            'click_rate': round(r.clicked / r.delivered, 4) if r.delivered else None,
        }
    def total(field):
        return sum(segment[field] for segment in breakdown.values())
    delivered = total('delivered_count')
    events_exist = db.scalar(select(DeliveryEvent.id).join(CampaignRecipient).where(
        CampaignRecipient.campaign_id == campaign_id).limit(1)) is not None
    result = {
        'campaign_id': campaign_id,
        'recipient_count': total('recipient_count'),
        'simulated_send_count': total('simulated_send_count'),
        'skipped_no_consent': total('skipped_no_consent'),
        'delivered_count': delivered,
        'unique_open_count': total('unique_open_count'),
        'unique_click_count': total('unique_click_count'),
        'unsubscribe_count': total('unsubscribe_count'),
        'open_rate': round(total('unique_open_count') / delivered, 4) if delivered else None,
        'click_rate': round(total('unique_click_count') / delivered, 4) if delivered else None,
        'by_persona': breakdown,
        'event_provenance': 'synthetic_demo' if events_exist else 'not_collected',
        'is_real_world_performance': False,
    }
    return result


def analyze_campaign(db: Session, campaign_id: str) -> dict:
    m = campaign_metrics(db, campaign_id)
    campaign = db.get(Campaign, campaign_id)
    if m['event_provenance'] == 'not_collected':
        message = (f'Campaign topic: {campaign.topic}. {m["simulated_send_count"]} mock sends were prepared, '
                   f'and {m["skipped_no_consent"]} contacts were suppressed. '
                   'No observed delivery events are available. Rates are intentionally null, '
                   'and no best-performing persona or causal optimization claim can be made.')
    else:
        message = (f'Campaign topic: {campaign.topic}. All events are synthetic demo fixtures, not '
                   f'customer activity. Recorded delivered={m["delivered_count"]}, '
                   f'unique opens={m["unique_open_count"]}, unique clicks={m["unique_click_count"]}. '
                   'These data demonstrate ingestion, deduplication and aggregation only; '
                   'they are not evidence of persona effectiveness.')
    db.add(PerformanceSummary(campaign_id=campaign_id, summary_text=message,
                              provenance=m['event_provenance']))
    db.commit()
    return {'campaign_id': campaign_id, 'provenance': m['event_provenance'], 'summary': message}
