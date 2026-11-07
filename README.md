# AKSHARA

**Intelligence Behind Every Document.**

AKSHARA is a document engineering platform for creating, editing, inspecting, standardising
and validating professional documents (DOCX, PDF, PPTX). Its core principle:
content quality + structural correctness + formatting compliance + visual quality.

> **Status: Phase 1 (Foundation) complete.** Accounts, secure upload, immutable storage,
> version records and the document library work end to end. Document analysis starts in
> Phase 2. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the plan and progress.

## Run it

### Option A — Docker (everything)

```bash
cp .env.example .env    # then set AKSHARA_JWT_SECRET and POSTGRES_PASSWORD
docker compose up -d --build
```

Open http://localhost:8080. Behind a TLS-inspecting proxy, add
`AKSHARA_EXTRA_CA_FILE=path/to/ca.pem` (a file inside the project folder) to the build command.

### Option B — Local development

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22, PostgreSQL 16 and Redis 7.

```bash
cp .env.example backend/.env    # point AKSHARA_DATABASE_URL at your database
make install
make migrate
make dev-api      # http://localhost:8000/api/docs
make dev-web      # http://localhost:5173
```

## Test

```bash
make lint            # ruff, mypy --strict, import-linter, tsc, eslint
make test            # backend unit + integration (real Postgres/Redis), frontend unit
make e2e SAMPLES=…   # browser end-to-end check, see e2e/README.md
```

## Layout

```
backend/    FastAPI app (api → services → adapters/db → domain), Alembic, Celery, tests
frontend/   React + TypeScript + Vite + Tailwind; React Bits components in components/reactbits
infra/      Dockerfiles and nginx
docs/       Architecture, ADRs
e2e/        Browser end-to-end checks
```
