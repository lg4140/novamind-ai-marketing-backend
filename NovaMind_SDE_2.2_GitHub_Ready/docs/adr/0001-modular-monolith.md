# ADR-0001: Modular Monolith + Optional Workers

**Status:** Accepted for demonstration. **Date:** 2026-10-14.

**Context:** Original system was a single sequential script with outbound calls, no durable task identity, and basic SQLite logging. Business scope still has one cohesive campaign domain.

**Decision:** Use FastAPI + service layer + SQLAlchemy in one deployable Python application. Add Celery/Redis workers and a transactional outbox for asynchronous tasks; keep SQLite inline mode for testability and PostgreSQL mode for integration practice.

**Consequences:** Faster development and simpler debugging than multi-service architecture; explicit modular boundaries facilitate future extraction. Outbox duplicate publication is tolerated by guarded state transitions. Production scheduling, queue observability and hard multi-tenant isolation remain separate work.
