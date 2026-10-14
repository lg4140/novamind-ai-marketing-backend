# Alembic 0003 migration — database compatibility and provenance

## Prerequisites
1. Create and verify a full database backup; stop API/Workers/Dispatcher (maintenance window).
2. Confirm current revision with `alembic current`; v2.1 should be `0002`.
3. Set `DATABASE_AUTO_CREATE=false` and run `alembic upgrade head`.
4. Run `alembic check` and the supported migration fixtures.
5. Spot-check `campaign_recipients` row count and unique constraints before reopening traffic.

## 0003 changes
- `campaigns`: add `generation_retry_count` (backfilled from lifetime `attempt`) and `content_revision_count` (derived from max content version - 1).
- `campaign_recipients`: add `persona_at_dispatch`, `content_version_id`, nullable `consent_at_dispatch`, `snapshot_source`, `dispatched_at` and Persona index.
- `outbox_events`: add `lease_owner` and `lease_until`.

## Honest migration semantics
For **old** recipient rows, past Persona is **unknown**. The migration copies the *current* Contact Persona and labels this `backfilled_current_profile`. If the Contact no longer exists, use `unknown`. Past consent remains **NULL** (not False/True) because it is not recoverable. Past dispatch timestamp is also NULL, and missing matching content versions remain NULL.

For **new** recipient rows, source is `captured_at_dispatch` and populated at dispatch time.

## Rollback strategy
Revision 0003 rejects destructive downgrade. Rollback requires an explicitly verified pre-migration backup. The migration creates nullable columns or safe backfill defaults, and batch-alters the content-version foreign key for SQLite compatibility. Validate staging migrations against the actual PostgreSQL version and operational data before rollout.

## Verification (tested locally)
`tests/test_migrations.py` contains legacy 0001→head and 0002→head cases. Both validate `alembic check`. The second proves old recipients remain and are labeled as unverified, with `consent_at_dispatch is None`.
