"""Prove that 2.0 records survive the explicit 0001 -> 0002 migration."""
import os
from pathlib import Path
import subprocess
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_schema_upgrade_preserves_campaign_and_content(tmp_path):
    db_file = tmp_path / 'upgrade.db'
    url = f'sqlite:///{db_file}'
    env = {**os.environ, 'DATABASE_URL': url, 'DATABASE_AUTO_CREATE': 'false',
           'APP_ENV': 'test'}
    def alembic(*args):
        return subprocess.run(['alembic', *args], cwd=ROOT, env=env,
                              text=True, capture_output=True, check=True)
    alembic('upgrade', '0001')
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO campaigns
          (id,idempotency_key,topic,personas,status,attempt,created_at,updated_at)
          VALUES ('old-campaign','old-key','Legacy workflow','["ops_lead"]',
          'COMPLETED',1,'2026-10-01','2026-10-01')'''))
        conn.execute(text('''INSERT INTO content_versions
          (id,campaign_id,prompt_version,provider,payload,created_at)
          VALUES ('old-content','old-campaign','v2','mock','{"blog_title":"Legacy"}',
          '2026-10-01')'''))
    alembic('upgrade', 'head')
    alembic('check')
    with engine.connect() as conn:
        row = conn.execute(text('''SELECT id,version_number,payload
          FROM content_versions WHERE campaign_id='old-campaign' ''')).one()
        assert row.id == 'old-content' and row.version_number == 1
        campaign = conn.execute(text('''SELECT status,approved_version_number,
          dispatch_attempt FROM campaigns WHERE id='old-campaign' ''')).one()
        assert campaign.status == 'COMPLETED'
        assert campaign.approved_version_number == 1
        assert campaign.dispatch_attempt == 0
    engine.dispose()


def test_v21_to_v22_preserves_recipients_and_labels_backfill(tmp_path):
    db_file = tmp_path / 'v21_snapshot.db'
    url = f'sqlite:///{db_file}'
    env = {**os.environ, 'DATABASE_URL': url, 'DATABASE_AUTO_CREATE': 'false', 'APP_ENV': 'test'}
    def alembic(*args):
        return subprocess.run(['alembic', *args], cwd=ROOT, env=env,
                              text=True, capture_output=True, check=True)
    alembic('upgrade', '0002')
    db_engine = create_engine(url)
    with db_engine.begin() as connection:
        connection.execute(text('''INSERT INTO campaigns
         (id,idempotency_key,topic,personas,status,attempt,dispatch_attempt,
          approved_version_number,created_at,updated_at)
         VALUES ('campaign21','key21','Historical campaign','["ops_lead"]',
                 'COMPLETED',2,1,1,'2026-10-01','2026-10-01')'''))
        connection.execute(text('''INSERT INTO contacts
        (id,email,firstname,lastname,company,persona_segment,marketing_consent)
        VALUES ('contact21','legacy@example.test','Old','Contact','Agency','ops_lead',1)'''))
        connection.execute(text('''INSERT INTO content_versions
        (id,campaign_id,version_number,prompt_version,provider,payload,created_at)
        VALUES ('version21','campaign21',1,'v21','mock','{}','2026-10-01')'''))
        connection.execute(text('''INSERT INTO campaign_recipients
        (id,campaign_id,contact_id,status,newsletter_subject,created_at)
        VALUES ('recipient21','campaign21','contact21','SIMULATED','Subject','2026-10-01')'''))
    alembic('upgrade', 'head')
    alembic('check')
    with db_engine.connect() as connection:
        record=connection.execute(text('''SELECT persona_at_dispatch, content_version_id,
        consent_at_dispatch, snapshot_source FROM campaign_recipients WHERE id='recipient21' ''' )).one()
        assert record.persona_at_dispatch=='ops_lead'
        assert record.content_version_id=='version21'
        assert record.consent_at_dispatch is None
        assert record.snapshot_source=='backfilled_current_profile'
        counts=connection.execute(text('''SELECT attempt,generation_retry_count,
        content_revision_count FROM campaigns WHERE id='campaign21' ''')).one()
        assert counts.attempt==2 and counts.generation_retry_count==2
        assert counts.content_revision_count==0
    db_engine.dispose()
