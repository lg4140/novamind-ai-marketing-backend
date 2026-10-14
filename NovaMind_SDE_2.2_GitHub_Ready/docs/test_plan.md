> **2.2 note:** This document originated in version 2.1. See `README.md`, `docs/upgrade_v22.md` and `docs/validation_v22.md` for current 2.2 behavior and evidence.

# Verification strategy — v2.1

## Tests executed locally

- Existing v2.0 API/business/security tests retained.
- New dispatch-failure regression: retry Dispatch without creating duplicate content.
- Expired Dispatch claim recovery: old execution marked TIMED_OUT; new claim runs.
- Synthetic unsubscribe with duplicated event ID and later CSV import: suppression stays effective.
- SQL Persona metrics: distinct recipient-level aggregate despite repeated open events.
- Worker consumer rejects unknown events and ignores duplicate generation jobs.
- Outbox publisher persists broker failure, postpones retry, then publishes when mock transport recovers.
- Content revision produces versions 1/2 and requires reapproval.
- Migration 0001 → 0002 with a legacy campaign/content fixture, followed by `alembic check`.
- Execution audit API authorization and privacy of its response.
- HTTP MockTransport test for CRM batch sizes and partial error flag.

## Next-tier tests not yet executed

1. PostgreSQL real concurrent `FOR UPDATE SKIP LOCKED` and lease-fencing tests with two separate workers.
2. Redis/Celery broker delivery, re-delivery after worker death and Dispatcher process crash between publish/commit.
3. Performance, saturation and long-running lease/heartbeat tests.
4. Genuine HubSpot staging contact-sync contract tests (never with private contacts in this reference).
5. Signed webhook ingestion and actual real email sender testing (neither implemented).
6. Docker Compose full-stack E2E and cloud deployment.

CI runs local mock tests, Alembic upgrade/drift, compile, Ruff's critical subset and Docker build. There is no verified strict mypy or comprehensive format gate in the shipped code.
