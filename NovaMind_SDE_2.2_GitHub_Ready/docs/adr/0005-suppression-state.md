# ADR 0005 — Durable suppression as an explicit business invariant

**Status:** accepted in v2.1

**Context:** v2.0 recorded unsubscribe events but did not affect future contact eligibility.

**Decision:** An authenticated-internal *synthetic* unsubscribe fixture sets `marketing_consent=false`, `suppression_reason='unsubscribed'` and `suppressed_at` transactionally. CSV import cannot restore revoked consent; actual consent recovery requires a future audited first-party mechanism.

**Consequences:** Future mock sends skip suppressed contacts. This does not establish legal consent for real email sending, nor implement a signed webhook.
