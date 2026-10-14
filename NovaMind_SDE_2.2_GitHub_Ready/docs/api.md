> **2.2 note:** This document originated in version 2.1. See `README.md`, `docs/upgrade_v22.md` and `docs/validation_v22.md` for current 2.2 behavior and evidence.

# API Contract — v2.1

All `/api/v1/*` endpoints require `Authorization: Bearer <token>`. POST `/campaigns` requires a stable `Idempotency-Key` unique to that request payload; collisions with changed payload yield 409.

| Method | Endpoint | Expected result |
| --- | --- | --- |
| POST | `/contacts/import` | validated contacts; no automatic live CRM sync |
| POST | `/contacts/sync-crm` | mock result unless explicit HubSpot flag/token |
| POST | `/campaigns` | create and generate inline or enqueue through outbox (202) |
| GET | `/campaigns/{id}` | status, generation/dispatch attempts, failure stage, approved version |
| GET | `/campaigns/{id}/content` | newest available numbered content version |
| POST | `/campaigns/{id}/revise` | new version, approval reset; valid only before dispatch |
| POST | `/campaigns/{id}/approve` | records latest content approval |
| POST | `/campaigns/{id}/dispatch` | mock-only send preparation |
| POST | `/campaigns/{id}/retry` | resume failed stage if retry budget remains |
| POST | `/campaigns/{id}/cancel` | cancel allowed non-executing state |
| GET | `/campaigns/{id}/executions` | max 100 sanitized attempt records |
| GET | `/campaigns/{id}/recipients` | recipient identifiers and mock statuses |
| GET | `/campaigns/{id}/metrics` | totals, by-persona, null rates if not observed |
| POST | `/campaigns/{id}/analysis` | deterministic synthetic-data-aware summary |
| POST | `/events/demo` | deduped synthetic delivered/opened/clicked/unsubscribed |

**State rule:** retry a failed `generation` back to `QUEUED`, a failed `dispatch` back to `DISPATCH_QUEUED`. `/revise` is not a retry: it invalidates prior approval and generates a new version. A campaign cannot be dispatched without content approval.

**Source rule:** all demo events are synthetic. The metrics field `is_real_world_performance` is always `false`. Actual provider delivery is not implemented.

Health `/health/live` is a process liveness endpoint, not an external dependency readiness guarantee.
