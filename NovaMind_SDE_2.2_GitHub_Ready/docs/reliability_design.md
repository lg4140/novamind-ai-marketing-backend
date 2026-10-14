> **2.2 note:** This document originated in version 2.1. See `README.md`, `docs/upgrade_v22.md` and `docs/validation_v22.md` for current 2.2 behavior and evidence.

# Reliability & fault-model design (v2.1)

## Failure stages and attempt budgets

`attempt` counts **generation** claims; `dispatch_attempt` counts **mock dispatch** claims. Both have a maximum of three. `failure_stage` is set when a stage throws. On `/retry`, generation failure returns to `QUEUED`; dispatch failure returns to `DISPATCH_QUEUED` and reuses `approved_version_number`. The choice is deterministic and explicit. User-triggered `/revise` is different from a failure retry: it creates another numbered content version, invalidates approval and forces review.

## Leases and stale-worker fencing

Each claimed stage persists `execution_token`, `lease_until` and an immutable-ish `execution_attempts` row. A finishing worker performs an UPDATE constrained by its token and current stage; after supervisor recovery a stale token cannot set the campaign status or save new content. `recover_stale()` handles both active stages. Exhausted tasks become `FAILED` with stage classification. The `recovery` Compose service polls every 10 seconds. Actual recovery occurs **after lease expiry**, not within ten seconds of failure.

**Limit:** no heartbeat extends the lease. The current default 300-second lease must exceed normal stage execution, or legitimate long workers could be fenced out. Always design provider calls with bounded timeouts. This safety mechanism governs DB outcomes, not a real external send; live email sending is deliberately unavailable.

## Outbox: at-least-once only

Business state and outbox intent commit atomically. The publisher fetches eligible PENDING rows and uses PostgreSQL `FOR UPDATE SKIP LOCKED` when present. Each publish result commits separately. Failure records category, increments attempts, and delays the next attempt exponentially (capped). Five failed publish attempts mark the outbox event FAILED for operator review.

Crash after broker publication and before DB commit can republish an event: worker operations compare expected campaign states, so duplicate generation/dispatch **mock** jobs are ignored. A stable Celery task ID equals the outbox ID, but this alone is **not** a broker-level deduplication guarantee. SQLite has no `SKIP LOCKED`; use one dispatcher in local demo.

## Event dedup and durable suppression

All demo events are explicitly synthetic. A unique `provider_event_id` prevents duplicate inserts. Delivered-first validation is enforced for synthetic opened/clicked/unsubscribed fixtures. Unsubscribe and suppression change commit in the same transaction. A subsequent CSV `marketing_consent=true` does not restore permission. A future real-provider callback must be authenticated and able to accept out-of-order delivery histories; **no real webhook is shipped**.

## Known boundaries

No provider-side send idempotency, ambiguous external outcome reconciliation, tenant-scoped identity, multi-region coordination, heartbeat, broker failover or distributed-load test is claimed. Outbox FAILED rows require manual operator intervention; no poison-message dashboard is provided. Existing migrated v2.0 FAILED rows have unclassified failure stages; they are deliberately not blindly replayed.
