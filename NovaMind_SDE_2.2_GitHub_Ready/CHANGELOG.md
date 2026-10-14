# Changelog

## 2.2.0 — 2026-10-14

### Fixed / Added
- Enforced SQLite foreign keys for each SQLAlchemy connection.
- Added immutable per-recipient Persona, approved version, consent snapshot and provenance; SQL metrics use the snapshot, not today's contact profile.
- Accept out-of-order synthetic delivered/engagement/unsubscribe events and enforce unsubscribed suppression immediately.
- Separated human content revisions from per-generation retry budget while preserving lifetime execution-attempt ordinals.
- Rebuilt Outbox publisher around short, committed claim transactions, expiring leases, publisher fencing and conservative at-least-once semantics.
- Added PostgreSQL/Celery best-effort heartbeat during content-generation calls.
- HubSpot contact sync now distinguishes confirmed per-item results from unknown outcomes; does not claim HTTP 200 means every contact succeeded.
- Strictly reject unknown request schema fields.
- Added Alembic `0003` with explicit legacy snapshot provenance, upgraded migration tests and regression tests (34 locally passing).

### Known limitations
- No real marketing email sending or real event webhook verification.
- PostgreSQL/Redis/Celery true multi-process fault injection, cloud deployment and performance benchmarks were not executed.
- CRM sync still synchronous and does not persist per-contact receipts. Use a durable background CRM Sync Job before large live batches.
- Historical values backfilled from current contacts are explicitly unverified; old consent is null.

---
# Change log — NovaMind SDE

## 2.1.0 (2026-10-14)

### Fixed / verified
- Dispatch failures no longer re-enter content generation and collide with the original content unique index; retries use the approved version.
- Stale `DISPATCHING` tasks are now recoverable alongside stale `GENERATING` tasks (mock-only safety boundary).
- Synthetic unsubscribe now persists a suppression record and blocks subsequent mock sends; CSV import cannot elevate suppressed contacts.
- Duplicate synthetic unsubscribe event IDs are no-ops; conflicting event IDs are rejected.
- Frozen v2.0 migration, v2.1 revision, preserved 2.0 fixture upgrade and schema-drift check.

### Added
- Stage-specific attempt counts, execution tokens, execution attempt audit log and read API.
- Explicit content revision endpoint with reapproval and numbered content versions.
- SQL-based distinct-recipient aggregate metrics and Persona breakdown.
- Outbox attempt/backoff/failure handling; periodic recovery process in Compose.
- Mocked HTTP provider, worker/outbox and regression tests; expanded runbook and engineering documentation.
- Localhost-only developer API bind in Compose.

### Still outstanding
- Full PostgreSQL/Redis/Celery running integration test in Docker, performance benchmark, operational dashboards and alerts.
- Real opt-in CRM sync staging test and robust per-record outcome persistence.
- Live marketing emails and verified webhooks are **not** implemented; legal consent/IAM/reconciliation would be required before development.
- Deep concurrency/chaos tests, production-grade type/lint gates and identity/RBAC.
