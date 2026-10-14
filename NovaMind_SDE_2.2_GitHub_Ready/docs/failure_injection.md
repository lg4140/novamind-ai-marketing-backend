> **Historical 2.1 reference:** See `docs/validation_v22.md` and `docs/migration_0003.md` for tested 2.2 behavior.

# Failure injection & reproducible debugging exercises

This is a **local mock** troubleshooting guide. Do not use real contacts, live email adapters or production credentials.

## Dispatch retry regression

`python -m pytest tests/test_v21_regressions.py::test_dispatch_failure_retry_reuses_approved_version -v`

The test overrides `MockMailer.send` to throw once, expects `status=FAILED`, `failure_stage=dispatch`, then retries into `DISPATCH_QUEUED`, resuming the approved version. It confirms there is no duplicate content row and only one campaign recipient.

## Expired Dispatch lease

`python -m pytest tests/test_v21_regressions.py::test_expired_dispatch_lease_recovers_and_fences_old_token -v`

The test claims Dispatch, moves `lease_until` into the past, executes the same recovery function the supervisor invokes, verifies the prior audit row is `TIMED_OUT`, and then performs mock Dispatch using the new execution token. Recovery is not instantaneous and does not bypass an unexpired lease.

## Outbox broker interruption

`python -m pytest tests/test_outbox_workers.py::test_outbox_retries_then_publishes_without_losing_event -v`

A fake broker throws an exception; the outbox stays pending and increments attempts. The test resets the simulated wait, uses a fake healthy publisher, verifies a successful publish and prevents re-publishing the already recorded row. This test does **not** simulate an actual Redis broker.

## Durable unsubscribe

`python -m pytest tests/test_v21_regressions.py::test_unsubscribe_blocks_future_campaign_even_after_csv_reimport -v`

Creates a synthetic delivered/unsubscribed event, replays the same ID, re-imports a CSV contact with consent=true, then proves the next mock campaign suppresses that contact.

## Legacy migration

`python -m pytest tests/test_migrations.py -v`

Uses an isolated SQLite database with legacy v2.0 schema and records, upgrades Alembic 0002, checks preserved IDs and version=1, and runs schema drift check. Repeat manually on a disposable PostgreSQL DB before deploying.

## Container fault injection (proposed, not executed in this delivery)

With Docker Compose stack running and only fictitious contacts: create a campaign in Celery mode; stop a worker during content generation; wait for the lease duration; check `execution_attempts` and recovery logs; restart worker and verify exactly one accepted final DB transition. Repeat for Dispatch, outbox Redis outage, and two-worker contention. Do not claim these pass until tests actually run on the target stack.
