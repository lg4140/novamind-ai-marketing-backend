from sqlalchemy import select
from app.db.models import ContentVersion, CampaignRecipient
from app.db.session import session_factory
from app.schemas import CampaignCreate
from app.services.campaigns import (create_campaign, process_generation,
    request_revision, approve_campaign, process_dispatch)


def test_revision_creates_v2_and_forces_fresh_approval():
    with session_factory()() as db:
        obj, _ = create_campaign(db, CampaignCreate(topic='AI content variants'), 'revisions')
        assert process_generation(db, obj.id)
        assert request_revision(db, obj.id).status == 'QUEUED'
        assert process_generation(db, obj.id)
        versions = db.scalars(select(ContentVersion).where(
            ContentVersion.campaign_id == obj.id).order_by(ContentVersion.version_number)).all()
        assert [x.version_number for x in versions] == [1,2]
        assert obj.status == 'REVIEW_REQUIRED' and obj.approved_version_number is None
        approve_campaign(db, obj.id)
        assert obj.approved_version_number == 2
        process_dispatch(db, obj.id)
        assert obj.status == 'COMPLETED'
        assert db.scalars(select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == obj.id)).all() == []
