# ADR 0006 — Frozen DDL migrations rather than mutable metadata

**Status:** accepted in v2.1

**Context:** importing current model metadata inside the v2.0 0001 migration broke historical reproducibility.

**Decision:** Generate and review a literal Alembic 0001 DDL snapshot; add data-preserving 0002; forbid automatic destructive downgrade; verify upgrade + Alembic drift in test.

**Consequences:** Migrations are audit-ready but SQLite and PostgreSQL must both be staged before deployment.
