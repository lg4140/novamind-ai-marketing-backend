# ADR 0007 — Immutable recipient snapshots

**Decision:** Store `persona_at_dispatch`, `content_version_id`, `consent_at_dispatch` and explicit snapshot provenance on CampaignRecipient; analytics group by historical recipient fields, not mutable Contact.

**Reason:** Existing v2.1 metrics drifted when Contacts were re-imported with a different Persona.

**Migration:** Historical Persona is backfilled from currently stored contacts but marked unverified; past consent remains NULL. New recipient records are captured at dispatch. Cost: duplicated small fields; benefit: stable reporting and auditable context.
