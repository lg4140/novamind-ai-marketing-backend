# NovaMind 2.3+ — evidence-driven remaining priorities

## P0 before any real email capability
- Keep MockMailer only until provider-specific send intents, pre-send consent recheck, provider idempotency/reconciliation and durable failure states are implemented.
- Build real webhook signature verification, event replay protection, durable unmatched-event quarantine, and independent Suppression Service.
- Replace development bearer token with identity provider and role-based permissions for importing contacts, approving content and CRM sync.

## P1 distributed reliability
- Execute PostgreSQL multi-publisher `SKIP LOCKED` contention and forced-kill tests, with Redis/Celery running in Docker.
- Add heartbeat/fencing integration tests for long generation calls; implement a bounded and recoverable Dispatch job with per-recipient intents before switching from MockMailer.
- Add durable asynchronous CRM Sync Job and per-item provider receipts; do not call a submission a confirmed sync without provider evidence.
- Measure worker wait/processing times, queue lag, retry exhaustion and error budget; wire tracing across request→Outbox→Worker.

## P2 delivery quality
- Upgrade CI to run PostgreSQL/Redis integration tests, `mypy`, strict Ruff, vulnerability scanning and reproducible lockfiles.
- Add SLOs and benchmark reproducibility with Locust or k6. Record p50/p95/p99, jobs/min, resources and environment details; never fabricate improvement percentages.
- Review security of contact retention/deletion, consent provenance and audit records; add a privacy policy for any live data.

## Acceptance gate for Production-Grade claim
Prove a repeatable 2-Worker/2-Publisher forced-failure suite, zero unexplained lost jobs, documented at-least-once behavior, provider-side deduplication/reconciliation for external effects, actionable telemetry, staged deployment and rollback. Until then label this project an engineering reference, not a live production email platform.
