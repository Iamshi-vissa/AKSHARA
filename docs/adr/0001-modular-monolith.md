# ADR 0001 — Modular monolith with Celery workers

Status: accepted (Phase 1)

**Context.** AKSHARA has many logical components (parsing, inspection, UDSE, correction,
generation...). Microservices would add network boundaries, deployment and consistency costs
before there is a team or scale that needs them.

**Decision.** One FastAPI application with strict internal layers
(`api → services → adapters | db → domain`), enforced in CI by `import-linter`. Heavy work
runs in Celery workers built from the same image.

**Consequences.** Simple deployment and transactions now; modules can be extracted later
along the enforced boundaries. The `domain` layer must stay free of I/O frameworks.
