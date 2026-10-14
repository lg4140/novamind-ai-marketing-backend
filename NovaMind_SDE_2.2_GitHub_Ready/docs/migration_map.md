> **Historical 2.1 reference:** See `docs/validation_v22.md` and `docs/migration_0003.md` for tested 2.2 behavior.

# Original project → SDE 2.1 migration map

| Original | v2.1 implementation | Why |
| --- | --- | --- |
| `main.py` | `app/api/routes.py`, `app/services/campaigns.py`, `app/workers/` | separate web, orchestration and background execution |
| `generate_content.py` | `app/integrations/ai.py` + `app/schemas.py` | typed content, deterministic mock, optional real model |
| `analyze_performance.py` | `app/services/analytics.py` | distinct event counts, Persona SQL aggregate, no invented metrics |
| `metrics.py` | synthetic events and SQL aggregation | explicit data provenance, correct denominators |
| `hubspot_client.py` | `app/integrations/hubspot.py` | opt-in CRM sync, bounded batch / errors, mock-only sends |
| `db.py` | `app/db/models.py`, `app/db/session.py`, `alembic/` | constraints, numbered content, audit and migrations |
| `config.py` | `app/core/config.py` | validated safe defaults and production guards |
| `contacts.csv` | `data/sample_contacts.csv` | public demo contains `.test` example data only; the original CSV is intentionally excluded from this public repo |
| `requirements.txt` | `pyproject.toml` | application/test dependency groups |
| `README.md` | `README.md`, `docs/`, ADRs, `CHANGELOG.md` | architecture decisions, runbooks and validation evidence |

**Preserved:** audience Personas, AI marketing content, CRM abstraction, campaign history and synthetic performance analysis. **Not copied into live operation:** the original transactional email send call and random engagement-rate generator. These were unsafe or misleading for the marketing use case.
