# NovaMind 2.2 — Measured validation record

Date: 2026-10-14. Runtime: local Python 3 environment with pytest, SQLAlchemy, Alembic and SQLite. This file reports **executed** checks, not projections.

| Validation | Result | Evidence |
|---|---|---|
| `python -m pytest -q` | 34 passed | v2.1 tests + new v2.2 regressions |
| `pytest --cov=app` | Approx. 80% | line coverage for local test execution |
| `python -m app.cli demo` | Passed | 6 fictional contacts; 5 mock sends; 1 no-consent skip; rates null without events |
| v2.0 0001→head migration | Passed | `test_legacy_schema_upgrade_preserves_campaign_and_content` |
| v2.1 0002→head migration | Passed | `test_v21_to_v22_preserves_recipients_and_labels_backfill` |
| Alembic model drift check | Passed in SQLite fixtures | `alembic check` subprocess |
| Historical persona immutability | Passed | Current profile changes do not affect past grouped metrics |
| FK enforcement | Passed | Orphan delivery event insertion raises IntegrityError |
| Out-of-order unsubscribe | Passed | Suppression persists before `delivered` and survives next Campaign |
| Outbox lease expiration and stale ack | Passed in SQLite fixture | Tokens fence stale claimant |
| HTTP 200 with partial item results | Passed with HTTPX MockTransport | Only correlated items CONFIRMED |
| Real PostgreSQL multi-dispatcher lock test | NOT executed | Docker/PostgreSQL unavailable in this run |
| Redis/Celery kill/restart/heartbeat test | NOT executed | Broker/Worker unavailable in this run |
| Real OpenAI/HubSpot | NOT executed | No real provider credentials/API side effects |
| Real marketing email sends | Disabled by design | MockMailer only |
| Performance benchmark / cloud deployment | NOT executed | Requires load test environment |

### Evidence limitations
- High coverage is not proof of multi-process safety. The new outbox tests verify state-machine invariants with SQLite, not PostgreSQL `SKIP LOCKED` races.
- In-memory CRM per-contact receipts are not durable; HubSpot contact sync is still synchronous.
- Real event security and legally sufficient consent workflows are out of scope.
