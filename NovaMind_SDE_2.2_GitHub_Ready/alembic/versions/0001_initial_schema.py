"""Frozen original v2.0 schema; never import current application metadata here.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('campaigns',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('idempotency_key', sa.String(length=128), nullable=False),
    sa.Column('topic', sa.String(length=250), nullable=False),
    sa.Column('personas', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_index(op.f('ix_campaigns_status'), 'campaigns', ['status'], unique=False)
    op.create_table('contacts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('firstname', sa.String(length=120), nullable=False),
    sa.Column('lastname', sa.String(length=120), nullable=False),
    sa.Column('company', sa.String(length=180), nullable=False),
    sa.Column('persona_segment', sa.String(length=50), nullable=False),
    sa.Column('marketing_consent', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('outbox_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outbox_events_status'), 'outbox_events', ['status'], unique=False)
    op.create_table('campaign_recipients',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('contact_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('newsletter_subject', sa.String(length=250), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id', 'contact_id', name='uq_campaign_contact')
    )
    op.create_index(op.f('ix_campaign_recipients_campaign_id'), 'campaign_recipients', ['campaign_id'], unique=False)
    op.create_table('content_versions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('prompt_version', sa.String(length=32), nullable=False),
    sa.Column('provider', sa.String(length=24), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id')
    )
    op.create_table('performance_summaries',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('summary_text', sa.Text(), nullable=False),
    sa.Column('provenance', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_performance_summaries_campaign_id'), 'performance_summaries', ['campaign_id'], unique=False)
    op.create_table('delivery_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider_event_id', sa.String(length=180), nullable=False),
    sa.Column('recipient_id', sa.String(length=36), nullable=False),
    sa.Column('event_type', sa.String(length=32), nullable=False),
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['recipient_id'], ['campaign_recipients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_event_id')
    )
    op.create_index(op.f('ix_delivery_events_recipient_id'), 'delivery_events', ['recipient_id'], unique=False)


def downgrade():
    op.drop_table('delivery_events')
    op.drop_table('performance_summaries')
    op.drop_table('content_versions')
    op.drop_table('campaign_recipients')
    op.drop_table('outbox_events')
    op.drop_table('contacts')
    op.drop_table('campaigns')
