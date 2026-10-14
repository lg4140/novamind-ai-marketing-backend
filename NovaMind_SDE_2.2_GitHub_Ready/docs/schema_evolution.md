> **Historical 2.1 reference:** See `docs/validation_v22.md` and `docs/migration_0003.md` for tested 2.2 behavior.

# Schema migration guide: v2.0 → v2.1

## Background

v2.0's `0001` migration called current `Base.metadata.create_all()`, making the historical revision mutable as the model evolved. In v2.1, `0001` is **frozen** as explicit DDL for the original seven domain tables. `0002_reliability_and_consent` is a distinct migration that preserves data and adds new constructs.

## Changes

| Entity | New attributes / behavior |
| --- | --- |
| campaigns | `failure_stage`, `dispatch_attempt`, `approved_version_number`, `execution_token` |
| content_versions | `version_number`, unique `(campaign_id,version_number)` replaces unique campaign ID |
| contacts | `suppression_reason`, `suppressed_at`, persona index |
| outbox_events | `attempts`, `last_error`, `next_attempt_at` |
| execution_attempts | new table: stage, attempt, token, status, error category, timestamps |

Migration `0002` recreates the content table in a cross-database way to remove an old unnamed SQLite unique constraint. It copies each historical row as version 1, then restores the table name and creates the new index. A v2.0 approved/completed campaign with content receives `approved_version_number=1`. Existing error rows have no trustworthy failure stage and must be investigated rather than automatically retried.

## Safe upgrade sequence

1. Take an actual database backup and validate that a restore works.
2. Stop API, worker, dispatcher and recovery services.
3. Confirm migration head and existing schema (`alembic current`).
4. Deploy the v2.1 source and set `DATABASE_AUTO_CREATE=false`.
5. Run `alembic upgrade head` with correct `DATABASE_URL`.
6. Run `alembic check`, API smoke tests and verify data counts/consent behavior.
7. Start the worker/dispatcher/recovery services; inspect FAILED campaigns and outbox rows.

The `tests/test_migrations.py` test executes frozen 0001, inserts a legacy campaign/content fixture, migrates to head, verifies data and runs `alembic check`. It is a **SQLite migration test**, not proof of a production PostgreSQL migration; repeat on disposable PostgreSQL before deployment.

## Downgrade policy

Automatic downgrade from 0002 is intentionally blocked because content revisions, suppressions and execution audit history cannot be represented in v2.0 without loss. Restore the verified backup if rollback is required.
