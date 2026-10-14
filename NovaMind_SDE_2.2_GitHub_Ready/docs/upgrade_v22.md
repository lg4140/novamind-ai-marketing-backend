# NovaMind 2.2 — Code-level engineering change record

## Ground truth: changes since 2.1

| 2.1 defect | 2.2 implementation | Source | Proof |
|---|---|---|---|
| Historical Persona drift | Snapshot `persona_at_dispatch` and group via recipient table | `models.py`, `campaigns.py`, `analytics.py` | `test_historical_persona_snapshot_unchanged_after_reimport` |
| SQLite Foreign Keys disabled | `connect` event executes `PRAGMA foreign_keys=ON` | `session.py` | `test_sqlite_enforces_foreign_key_references` |
| Unsubscribe rejected before Delivered | Accept out-of-order synthetic events, independent suppression | `analytics.py` | `test_unsubscribe_before_delivered_suppresses_future_campaigns` |
| Revision and retry shared budget | `content_revision_count`, `generation_retry_count`, lifetime `attempt` | `models.py`, `campaigns.py` | `test_content_revision_has_separate_budget_from_execution_retry` |
| Batch row lock released mid-outbox | Commit claim tokens before all broker calls | `workers/outbox.py` | leased state/fencing tests (SQLite; PostgreSQL unverified) |
| Long generator call may expire lease | Conditional heartbeat in PostgreSQL/Celery mode | `workers/leases.py`, `campaigns.py` | manual renewal CAS tested; real Celery heartbeat remains unverified |
| HubSpot submit mistaken for success | Per-item CONFIRMED/UNCONFIRMED result correlation | `integrations/hubspot.py` | `test_crm_does_not_treat_200_empty_results_as_confirmed` |
| Unrecognized payload fields ignored | Pydantic `extra=forbid` | `schemas.py` | `test_api_rejects_unknown_request_fields` |

## Architectural decision details

### Immutable snapshot, not temporal profile reconstruction
A CampaignRecipient captures the segment at dispatch; its linked Contact may subsequently change. Old rows had no true snapshot; migration 0003 tags `backfilled_current_profile` and null consent. This avoids false confidence about the past. A future version could adopt bitemporal profiles if business requirements demand reconstructing every past edit.

### Safe event ordering
Synthetic source events may arrive before `delivered`. We preserve each distinct provider event and deduplicate by ID. The suppression path is independent of analytics event order. `open_rate` and `click_rate` are null without a delivered denominator. The synthetic endpoint is credential protected and disabled in production; real webhooks still require verified signature, replay protection and Provider mapping.

### Outbox `PUBLISHING` lease
The dispatcher claims a bounded set of rows with conditional UPDATE under a short transaction. It commits claims and then invokes broker operations outside that transaction. Ack/fail uses the unique lease token to avoid stale writers. On crash the lease becomes eligible for replay. Replays can publish the same task more than once; Campaign execution state + tokens guard consumers.

### Attempt budget separation
`Campaign.attempt` remains an ever-increasing generation execution ordinal, and new `generation_retry_count` is reset on each new human revision. `content_revision_count` tracks human revisions with a separate generous cap of 100. `dispatch_attempt` remains independent; in a later version these counters should move into a dedicated ExecutionRun entity.

### Limitations explicitly preserved
- No live email dispatch; the MockMailer is intentionally not an integration abstraction safe to swap in production.
- CRM contact synchronization remains synchronous, and its `item_results` are an in-memory response, not persisted receipts.
- Not yet validated: PostgreSQL two-Dispatcher race, Redis outages, Worker kills, heartbeat renewals, load testing, IAM, real event signatures.
