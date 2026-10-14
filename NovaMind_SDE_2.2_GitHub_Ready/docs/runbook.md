> **2.2 note:** This document originated in version 2.1. See `README.md`, `docs/upgrade_v22.md` and `docs/validation_v22.md` for current 2.2 behavior and evidence.

# v2.1 Operations Runbook

## Start local reference

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -e '.[dev]' && cp .env.example .env`
3. `python -m app.cli demo`
4. `python -m pytest -q`
5. `uvicorn app.main:app --reload` then use `/docs` with the **development** token.

## Container development (not independently verified in this delivery environment)

`docker compose up --build` defines PostgreSQL, Redis, migration, API, worker, dispatcher and periodic recovery. Seed only synthetic contacts with `docker compose exec api python -m app.cli seed`. Review logs separately: `docker compose logs -f api worker dispatcher recovery migrate`. `docker compose down -v` destroys local DB volume and should not be used on valuable data.

## Upgrade existing data

Back up and test restore, stop write-producing services, set `DATABASE_AUTO_CREATE=false`, run `alembic upgrade head`, `alembic check`, smoke-test, then resume workers. See `schema_evolution.md`. SQLite local DB migration was tested with legacy fixture; PostgreSQL not verified here.

## Failure decision table

| Situation | Diagnosis / action |
| --- | --- |
| `FAILED` and `failure_stage=generation` | Fix OpenAI/mock input or config; `/retry` if remaining attempt budget |
| `FAILED` and `failure_stage=dispatch` | Verify the mock-only environment; `/retry` resumes Dispatch without regenerating content |
| `FAILED` and no stage (migrated legacy data) | Manual analysis, do not replay blindly |
| `GENERATING` or `DISPATCHING` after worker death | Wait for lease expiry; `recover-stale` or Compose recovery service; inspect execution attempts |
| Outbox `PENDING` with `next_attempt_at` | Wait for bounded backoff; inspect Redis and dispatcher |
| Outbox `FAILED` | Manually inspect and remediate; no automated replay UI is provided |
| API 401 | Check token but never log the secret; production requires stronger identity infrastructure |
| Demo click/open with no delivered event | Submit synthetic delivered event first; real webhooks not supported |
| CRM batch reports `requires_reconciliation` | Review provider results in staging; no per-contact receipt persistence yet |

## Operator queries (read-only)

```sql
SELECT status, failure_stage, COUNT(*) FROM campaigns GROUP BY status, failure_stage;
SELECT stage, status, COUNT(*) FROM execution_attempts GROUP BY stage, status;
SELECT status, COUNT(*) FROM outbox_events GROUP BY status;
SELECT suppression_reason, COUNT(*) FROM contacts GROUP BY suppression_reason;
```

No real marketing-email sending is implemented. Do not replace `MockMailer` with a live provider without verified consent, authorization, deduplication and ambiguous-outcome recovery.
