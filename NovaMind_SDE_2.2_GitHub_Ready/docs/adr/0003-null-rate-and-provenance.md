# ADR-0003: Provenance and Nullable Rates

**Status:** Accepted; **Date:** 2026-10-14.

**Context:** Legacy `metrics.py` independently sampled floating-point rates and rounded events to integers. With two contacts per persona, click count could be zero while reported click rate was nonzero.

**Decision:** Compute rates only from deduplicated delivery events; use unique event-recipient counts and a delivered denominator. If no delivery is recorded, report null, not zero. Expose provenance (`not_collected` or `synthetic_demo`) and always flag `is_real_world_performance=false`.

**Consequences:** Prevents unsupported claims of campaign effectiveness. Actual production tracking requires signed verified provider events and operational monitoring before expanding provenance types.
