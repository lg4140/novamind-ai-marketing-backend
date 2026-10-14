"""Execution fencing, stage-aware retries, durable suppression and content revisions.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('campaigns', sa.Column('failure_stage', sa.String(24)))
    op.add_column('campaigns', sa.Column('dispatch_attempt', sa.Integer(), nullable=False,
                                         server_default=sa.text('0')))
    op.add_column('campaigns', sa.Column('approved_version_number', sa.Integer()))
    op.add_column('campaigns', sa.Column('execution_token', sa.String(36)))
    op.add_column('contacts', sa.Column('suppression_reason', sa.String(64)))
    op.add_column('contacts', sa.Column('suppressed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_contacts_persona_segment', 'contacts', ['persona_segment'])
    op.add_column('outbox_events', sa.Column('attempts', sa.Integer(), nullable=False,
                                             server_default=sa.text('0')))
    op.add_column('outbox_events', sa.Column('last_error', sa.String(200)))
    op.add_column('outbox_events', sa.Column('next_attempt_at', sa.DateTime(timezone=True)))
    # Cross-database rebuild avoids relying on SQLite's unnamed 2.0 unique constraint.
    # No other v2.0 table references content_versions by FK.
    op.create_table('content_versions_upgrade',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('campaign_id', sa.String(36), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('prompt_version', sa.String(32), nullable=False),
        sa.Column('provider', sa.String(24), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('campaign_id', 'version_number', name='uq_content_campaign_version'))
    op.execute('''INSERT INTO content_versions_upgrade
        (id,campaign_id,version_number,prompt_version,provider,payload,created_at)
        SELECT id,campaign_id,1,prompt_version,provider,payload,created_at FROM content_versions''')
    op.drop_table('content_versions')
    op.rename_table('content_versions_upgrade', 'content_versions')
    op.create_index('ix_content_versions_campaign_id', 'content_versions', ['campaign_id'])
    op.execute('''UPDATE campaigns SET approved_version_number=1
                  WHERE status IN ('APPROVED','DISPATCH_QUEUED','DISPATCHING','COMPLETED')
                  AND id IN (SELECT campaign_id FROM content_versions)''')
    op.create_table('execution_attempts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('campaign_id', sa.String(36), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('stage', sa.String(24), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('execution_token', sa.String(36), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('error_category', sa.String(100)),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('campaign_id','stage','attempt_number',name='uq_execution_attempt'))
    op.create_index('ix_execution_attempts_campaign_id','execution_attempts',['campaign_id'])


def downgrade():
    # Destructive downgrade intentionally blocked: multiple content versions and
    # suppression/attempt audit records cannot be represented in the old schema.
    raise RuntimeError('Downgrade from 0002 would lose audit data. Restore a backed-up 0001 DB.')
