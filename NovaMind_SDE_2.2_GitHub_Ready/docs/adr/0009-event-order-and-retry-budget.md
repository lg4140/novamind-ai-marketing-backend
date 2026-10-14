# ADR 0009 — Out-of-order events and independent user revisions

**Decision:** Accept synthetic events in arbitrary order. Persist unsubscribe suppression independently from delivered/opened analytics. Separate content revision count, per-revision generation retry count and lifetime execution ordinal.

**Reason:** Real webhooks may arrive out of order; unsubscribe must not be dropped because delivery was late. Human revision is not an execution failure.

**Scope:** Only synthetic authenticated demo events; verified real provider webhooks require separate integration design.
