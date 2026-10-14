> **Historical 2.1 reference:** See `docs/validation_v22.md` and `docs/migration_0003.md` for tested 2.2 behavior.

# Local validation evidence — 2026-10-14 · NovaMind SDE 2.1

**Scope of execution:** Python 3.13, SQLite local files, deterministic mock AI and mailer; HTTP adapter uses `httpx.MockTransport`; Celery broker publication is mocked in unit tests. **Real PostgreSQL/Redis/Celery containers, real HubSpot/OpenAI network calls and production load tests were not executed.**

## Commands and measured output

```text
python -m compileall -q app tests           PASSED
python -m pytest -q --cov=app --cov-report=term --cov-fail-under=75
                                              24 passed (5–6 seconds)
                                              TOTAL: 848 statements; 180 uncovered
                                              COVERAGE: 78.77% (~79%)
python -m app.cli demo                       PASSED
                                              imported=6, simulated_send_count=5,
                                              skipped_no_consent=1,
                                              delivered=0, open/click rates=null
PostgreSQL/Redis/Celery Docker E2E           NOT RUN
Real HubSpot CRM staging integration          NOT RUN
Real OpenAI provider integration              NOT RUN
Real marketing email delivery                 NOT IMPLEMENTED
```

Migration test (`tests/test_migrations.py`) executes literal Alembic 0001, inserts a v2.0 campaign and content row, upgrades to 0002 and runs `alembic check`; source campaign/content IDs and content payload are preserved, with version=1 and approved_version=1.

Tests specifically cover:

- Original API auth, idempotent campaign create and approval gates.
- Failure of MockMailer during dispatch, then stage-appropriate retry with no duplicate content version.
- Expired Dispatch lease recovery, `TIMED_OUT` audit row and successful replay.
- Persistent unsubscribe after duplicate demo event and later CSV import that requests new consent.
- SQL-based per-Persona distinct-recipient event aggregation (two opens from one person count as one).
- Outbox transient broker failure/backoff then successful mocked publication.
- Celery consumer duplicate generation and unknown event handling (without real Redis).
- Content revision creates versions 1/2 and forces new approval.
- Sanitized execution audit endpoint and missing auth rejection.
- HTTP `MockTransport` verifies HubSpot batches (100 + 2 contacts) and partial error flag.

## Coverage and warning interpretation

Application total ~79%. High-value `services/campaigns.py` approximately 87%, `workers/outbox.py` approximately 87%, and `workers/tasks.py` approximately 72%; CLI still 0% under pytest because its demo was exercised separately as a shell smoke test. A non-fatal `ResourceWarning` about an SQLite connection appeared in one coverage run; it does not invalidate assertions, but connection lifecycle should be reviewed in further tests.

No p95 latency, throughput, cost reduction, delivery uplift or fault-tolerance SLO was measured. No such result should be claimed in a resume or presentation.

## Limitations / required external staging

- Full Compose startup, Alembic upgrade and service E2E on PostgreSQL/Redis.
- Multi-worker crash injection, lease boundary races, heartbeats and false-positive lease reclaim.
- Outbox crash exactly between `apply_async` and DB commit and broker retry settings.
- Actual HubSpot contact sync and per-contact error mapping; signed real webhooks do not exist.
- Production identity, consent provenance, PII lifecycle and approved marketing-email provider design.
