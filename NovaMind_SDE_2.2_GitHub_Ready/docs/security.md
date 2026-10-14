> **2.2 note:** This document originated in version 2.1. See `README.md`, `docs/upgrade_v22.md` and `docs/validation_v22.md` for current 2.2 behavior and evidence.

# Security and privacy boundary — v2.1

- All API business endpoints require a simple Bearer token. This is **demo authentication** only, not OAuth, RBAC, tenant isolation or a complete identity system.
- `APP_ENV=production` rejects example API token, automatic table creation and synthetic event ingestion. The container Compose stack is **development** and exposes the API on 127.0.0.1:8000 only.
- Neither existing customer CSV nor HubSpot mock records grant real marketing permissions. User-contact data can be sensitive; no real contacts should be uploaded until retention, audit and encryption policies are implemented.
- Demo event ingestion is never a verified provider webhook. It is turned off in production. No real email sending exists.
- An `unsubscribed` demo event persists a suppression; CSV reimport cannot restore it. Implementing a legally sufficient re-consent process is future work.
- Secrets belong in local `.env` for development and an external secret manager in staging/production. `.env` should not be committed. Avoid logging Authorization headers, full contact payloads or AI prompt PII.
- HubSpot CRM contact sync can be enabled only via explicit flags and token. Batch sync results are not sufficient proof of successful per-contact state; check reconciliation before production use.
- Worker lease tokens guard DB state but do not make external side effects exactly once. Any live send adapter requires a separate reconciliation and approval design.
