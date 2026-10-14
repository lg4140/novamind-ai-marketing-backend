# ADR 0008 — Claim/publish/ack Outbox

**Decision:** Use short transactional claims with lease token and expiration. Publish outside DB transaction; acknowledge with token after broker call.

**Reason:** Batch row locks previously expired on per-event commits, permitting multiple Dispatchers to publish overlapping events. Commit-before-publish prevents long DB locks; lease permits recovery after crash.

**Guarantee:** At-least-once publication, NOT exactly-once. Client/consumer idempotency and operation reconciliation remain mandatory. SQLite is a mock demonstrator, not concurrency evidence.
