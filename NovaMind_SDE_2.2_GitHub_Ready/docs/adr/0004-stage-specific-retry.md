# ADR 0004 — Stage-specific retry and execution fencing

**Status:** accepted in v2.1

**Context:** A failed Dispatch retried through generation in v2.0 and violated one-content-per-campaign uniqueness. `DISPATCHING` also had no stale-worker recovery.

**Decision:** Track `failure_stage`, separate generation/dispatch budgets, persist tokenized execution attempts, retry only the failed stage, and recover expired leases in both stages. Never retry any actual external email outcome without reconciliation (current implementation has no live email).

**Consequences:** Clear audit trail and guarded retries; added schema and recovery complexity. Lease durations and operator review remain important.
