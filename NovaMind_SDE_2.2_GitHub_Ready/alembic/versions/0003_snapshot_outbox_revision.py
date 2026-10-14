"""Recipient history snapshots, outbox lease and independent revision attempts.

Revision ID: 0003
Revises: 0002

Historical personas are backfilled from CURRENT contact data as an explicitly
unverified approximation. Past consent cannot be inferred and stays NULL.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('campaigns', sa.Column('generation_retry_count', sa.Integer(),
                                       nullable=False, server_default=sa.text('0')))
    op.add_column('campaigns', sa.Column('content_revision_count', sa.Integer(),
                                       nullable=False, server_default=sa.text('0')))
    op.execute('UPDATE campaigns SET generation_retry_count=attempt')
    op.execute('''UPDATE campaigns SET content_revision_count=COALESCE(
         (SELECT MAX(version_number) - 1 FROM content_versions v
          WHERE v.campaign_id=campaigns.id), 0)''')
    op.add_column('campaign_recipients', sa.Column('persona_at_dispatch', sa.String(50),
                                                 nullable=False, server_default='unknown'))
    with op.batch_alter_table('campaign_recipients') as batch:
        batch.add_column(sa.Column('content_version_id', sa.String(36),
                                   sa.ForeignKey('content_versions.id', name='fk_recipients_content_version'), nullable=True))
    op.add_column('campaign_recipients', sa.Column('consent_at_dispatch', sa.Boolean(), nullable=True))
    op.add_column('campaign_recipients', sa.Column('snapshot_source', sa.String(40),
                   nullable=False, server_default='backfilled_current_profile'))
    op.add_column('campaign_recipients', sa.Column('dispatched_at', sa.DateTime(timezone=True)))
    # Backfill is NOT evidence of the historical persona. Unknown remains unknown.
    op.execute('''UPDATE campaign_recipients SET persona_at_dispatch=COALESCE(
         (SELECT c.persona_segment FROM contacts c WHERE c.id=campaign_recipients.contact_id),
         'unknown')''')
    op.execute('''UPDATE campaign_recipients SET content_version_id=(
         SELECT v.id FROM content_versions v JOIN campaigns ca ON ca.id=v.campaign_id
         WHERE v.campaign_id=campaign_recipients.campaign_id
         AND v.version_number=ca.approved_version_number)''')
    op.create_index('ix_campaign_recipients_persona_snapshot', 'campaign_recipients',
                    ['campaign_id', 'persona_at_dispatch'])
    op.add_column('outbox_events', sa.Column('lease_owner', sa.String(36)))
    op.add_column('outbox_events', sa.Column('lease_until', sa.DateTime(timezone=True)))


def downgrade():
    raise RuntimeError('Downgrade from 0003 would discard immutable history and leases; restore backup.')
