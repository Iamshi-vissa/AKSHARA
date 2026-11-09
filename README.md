# AKSHARA

**Intelligence Behind Every Document.**

AKSHARA is a document engineering platform for creating, inspecting, standardising and validating
professional documents (DOCX, PDF and PPTX).

> **Status: Phase 1 of 9 (Foundation) is complete.** Accounts, secure upload, immutable storage,
> version history and the document library work end to end. Document analysis starts in Phase 2.
> See the [roadmap](#status-and-roadmap) below.

## About

Most document tools check either the words or the layout. AKSHARA is built to check both: whether
the content is good, whether the structure is correct (headings, numbering, references), whether
it follows a required standard such as IEEE or APA, and whether it looks right on the page.

Today it gives you a safe place to upload and keep documents. Every file is checked before it is
accepted, stored so it can never be silently changed, and kept with its full version history. The
inspection, standards and editing features are designed and scheduled, but not built yet.

## Features (available now)

- **Accounts:** sign up and log in, with short-lived access tokens, rotating refresh tokens and
  rate-limited login.
- **Safe uploads:** each file's real type is checked from its contents, macros are rejected, and
  size and zip-bomb limits are enforced before anything is stored.
- **Immutable storage:** files are stored on disk by content hash, so a stored version can never
  change. (S3 storage is planned but not built yet.)
- **Versions and audit trail:** every upload creates a version record, and every action is logged.
- **Document library:** a web page listing your documents and their versions.

## Tech stack

| Part | Tools |
|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy (async), Alembic, Pydantic |
| Background jobs | Celery, Redis |
| Database and storage | PostgreSQL 16, local disk |
| Frontend | React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Bits |
| Tooling | uv, ruff, mypy (strict), import-linter, pytest, Vitest, ESLint, Docker, GitHub Actions |

## Getting started

### Option A: Docker (everything in one command)

You need Docker with Compose.

```bash
cp .env.example .env    # then set AKSHARA_JWT_SECRET and POSTGRES_PASSWORD
docker compose up -d --build
```

Open http://localhost:8080. Behind a TLS-inspecting proxy, add
`AKSHARA_EXTRA_CA_FILE=path/to/ca.pem` (a file inside the project folder) to the build command.

### Option B: Local development

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22, PostgreSQL 16 and Redis 7.

```bash
cp .env.example backend/.env    # point AKSHARA_DATABASE_URL at your database
make install                    # backend (uv) and frontend (npm) dependencies
make migrate                    # create the database tables
make dev-api                    # API on http://localhost:8000 (docs at /api/docs)
make dev-web                    # web UI on http://localhost:5173
```

### Configuration

All settings live in `.env` (see [`.env.example`](.env.example) for every option). The two you must
set are `AKSHARA_JWT_SECRET` and `POSTGRES_PASSWORD`. Set `AKSHARA_COOKIE_SECURE=true` whenever the
app runs behind HTTPS.

## Running the tests

```bash
make lint            # ruff, mypy --strict, import-linter, tsc, eslint
make test            # backend unit + integration tests, frontend unit tests
make e2e SAMPLES=…   # browser end-to-end check (see e2e/README.md)
```

The backend integration tests use a real PostgreSQL and Redis. Create the test database once
before the first run (see [`backend/tests/README.md`](backend/tests/README.md)):

```bash
createdb -O akshara akshara_test
```

## Project structure

```
backend/    FastAPI app (api → services → adapters/db → domain), Alembic migrations, Celery, tests
frontend/   React + TypeScript + Vite + Tailwind; React Bits components in components/reactbits
infra/      Dockerfiles and nginx
docs/       Architecture document and decision records (ADRs)
e2e/        Browser end-to-end checks
```

The backend follows a strict layered design, and `import-linter` fails the build if a layer
imports one it shouldn't. The full design is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Status and roadmap

| Phase | What it adds | Status |
|---|---|---|
| 1. Foundation | Accounts, secure upload, immutable storage, versions, library | ✅ Done |
| 2. Document intelligence | Read DOCX, PDF and PPTX into one model; render and preview pages | Not started |
| 3. Inspection engine | Structure and formatting checks with a quality report | Not started |
| 4. Standards (UDSE) | IEEE, APA and MLA rule profiles with compliance reports | Not started |
| 5. Editing and correction | Tracked AI and grammar edits, approval-gated auto-fixes | Not started |
| 6. Document generation | Draft ten document types from a brief; export to DOCX and PDF | Not started |
| 7. Presentation engine | Generate PPTX decks with themes, layouts and speaker notes | Not started |
| 8. Visual quality engine | Find visual defects on rendered pages and slides | Not started |
| 9. Research and advanced AI | Source discovery, reference checks, custom standard builder | Not started |

## License

No license has been added yet, so all rights are reserved by default.
