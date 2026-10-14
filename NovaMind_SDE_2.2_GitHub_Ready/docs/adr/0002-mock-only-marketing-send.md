# ADR-0002: No Live Marketing Send in v2 Reference

**Status:** Accepted for safety; **Date:** 2026-10-14.

**Context:** Legacy code used a transactional single-email endpoint for conceptual persona newsletters without evidence of subscription state, verified marketing-template configuration or delivery feedback.

**Decision:** Keep only a `MockMailer`; dispatch produces durable `SIMULATED` or `SKIPPED_NO_CONSENT` states. Provide a separately gated HubSpot CRM contact sync. Synthetic events are independently labeled. Any production marketing adapter must be reviewed for provider semantics, consent, unsubscribe, suppression, per-recipient idempotency and webhook signatures.

**Consequences:** This project is safe to demonstrate without sending real emails, but cannot claim real marketing delivery or optimization gains. Transparent non-goal is preferable to a misleading production-readiness claim.
