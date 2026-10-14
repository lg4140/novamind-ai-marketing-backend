# Security policy

NovaMind is a **demonstration/reference implementation**, not a production-grade marketing system. It does not send real marketing emails. Do not deploy the development Compose file publicly or use it with real customer contacts.

## Safe setup

- Keep `.env`, live CRM tokens, API keys, credentials, customer exports, database backups and logs out of Git. The repository includes only `.env.example` and fictional `@example.test` sample contacts.
- Change the example API token before any externally accessible deployment. `APP_ENV=production` has additional validation, but **does not** provide full IAM/RBAC, tenant isolation or production readiness.
- CRM sync is opt-in and does **not** send email. Do not enable it with real data without permission, retention and security review.
- Do not submit real personal information in public issues, logs or screenshots.

## Reporting issues

For security concerns, prefer GitHub's private vulnerability reporting (if enabled for the repository) rather than a public issue containing exploit details or credentials. There is no security support SLA for this portfolio project.
