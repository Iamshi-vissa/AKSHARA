# <img src="docs/headers/h1-akshara.svg" alt="AKSHARA" height="60">

A platform for checking, fixing and creating professional documents (DOCX, PDF and PPTX).

> **Status:** early. *Phase* 1 of 9 is finished: accounts, secure uploads, *version* history and the
> document library work end to end. Document analysis starts in Phase 2.

## <img src="docs/headers/h2-about.svg" alt="ABOUT" height="38">

Reports, theses and slide decks often have to follow strict rules: heading levels, numbering,
captions, margins, fonts and citation styles such as IEEE or APA. Checking all of that by hand is
slow and easy to get wrong.

AKSHARA is being built to do that work. You upload a document, it reads the structure, checks it
against a *standard*, explains what's wrong, and offers fixes you approve one by one. Later phases add
writing new documents and slide decks from a short brief.

Every uploaded file is kept as an unchangeable original, and each edit creates a new *version*, so
nothing is ever lost.

## <img src="docs/headers/h2-what-works-today-phase-1.svg" alt="WHAT WORKS TODAY (PHASE 1)" height="38">

- Sign up and log in, with secure sessions and rate-limited login
- Upload DOCX, PDF and PPTX files up to 50 MB
- Safety checks on every upload: real file type from the contents, size limits, protection against
  *zip bombs*, and rejection of files with *macros*
- Original files stored once and never changed, with a *version* record for each one
- A document library with search, plus dashboard and settings pages

## <img src="docs/headers/h2-planned-phases.svg" alt="PLANNED PHASES" height="38">

| Phase | What it adds |
|---|---|
| 2. Document intelligence | Read all three formats into one internal model and preview the pages |
| 3. Inspection | Find structure and formatting problems, graded by severity, with a quality report |
| 4. Standards | Built-in IEEE, APA and MLA rule sets, custom rules and compliance reports |
| 5. Editing | Tracked edits and grammar fixes, and automatic corrections you approve first |
| 6. Generation | Write documents from a brief, section by section, and export to DOCX or PDF |
| 7. Presentations | Generate slide decks with themes, layouts and speaker notes |
| 8. Visual checks | Spot layout problems such as text running off the page or blank pages |
| 9. Research | Find and verify sources and references |

The full plan is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), with design decisions in
[docs/adr](docs/adr).

## <img src="docs/headers/h2-how-it-works.svg" alt="HOW IT WORKS" height="38">

1. The React web app sends the file to the API.
2. The API checks the file is safe and really is the type it claims to be.
3. The file is stored by its content hash, so the same file is never stored twice, and a *version*
   record is added to PostgreSQL.
4. Slower work will run in background workers through Celery and Redis. The worker is set up and
   tested in *Phase* 1, but the real jobs (parsing and checking) arrive in Phases 2 and 3.

## <img src="docs/headers/h2-architecture.svg" alt="ARCHITECTURE" height="38">

```mermaid
flowchart LR
    U[React web app] --> N[nginx]
    N --> API[FastAPI routes]
    API --> SV[Services]
    SV --> D[Domain rules, no I/O]
    SV --> DB[(PostgreSQL)]
    SV --> BL[(File storage by content hash)]
    API --> Q[(Redis)]
    Q --> CW[Celery workers]
```

The code is layered: routes call services, services call the database and storage, and the core rules never touch I/O. An automated check keeps those layers apart.

## <img src="docs/headers/h2-tech-stack.svg" alt="TECH STACK" height="38">

<p align="center">
  <img src="https://img.shields.io/badge/Python-000000?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-000000?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-000000?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Redis-000000?style=flat-square&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/Celery-000000?style=flat-square&logo=celery&logoColor=white" alt="Celery">
  <img src="https://img.shields.io/badge/SQLAlchemy-000000?style=flat-square&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/React-000000?style=flat-square&logo=react&logoColor=white" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-000000?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Vite-000000?style=flat-square&logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/Tailwind%20CSS-000000?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/nginx-000000?style=flat-square&logo=nginx&logoColor=white" alt="nginx">
  <img src="https://img.shields.io/badge/Docker-000000?style=flat-square&logo=docker&logoColor=white" alt="Docker">
</p>

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, Pydantic |
| Data | PostgreSQL 16, SQLAlchemy, Alembic |
| Background jobs | Celery, Redis 7 |
| Web app | React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Bits |
| Infrastructure | Docker Compose, nginx |
| Quality | pytest, Vitest, ruff, mypy (strict), import-linter, ESLint |

## <img src="docs/headers/h2-getting-started.svg" alt="GETTING STARTED" height="38">

### <img src="docs/headers/h3-with-docker-easiest.svg" alt="WITH DOCKER (EASIEST)" height="28">

```bash
git clone https://github.com/Iamshi-vissa/Akshara.git
cd Akshara
cp .env.example .env    # then set AKSHARA_JWT_SECRET and POSTGRES_PASSWORD
docker compose up -d --build
```

Open <http://localhost:8080>.

To make a JWT secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

### <img src="docs/headers/h3-for-local-development.svg" alt="FOR LOCAL DEVELOPMENT" height="28">

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22, PostgreSQL 16 and Redis 7.

```bash
cp .env.example backend/.env    # point AKSHARA_DATABASE_URL at your database
make install                    # backend and frontend dependencies
make migrate                    # create the database tables
make dev-api                    # API at http://localhost:8000/api/docs
make dev-web                    # web app at http://localhost:5173
```

Run `make help` to see every command.

## <img src="docs/headers/h2-running-the-tests.svg" alt="RUNNING THE TESTS" height="38">

```bash
make lint     # ruff, mypy, import-linter, TypeScript and ESLint
make test     # 81 backend tests (needs PostgreSQL and Redis) and 13 frontend tests
```

The backend tests create and delete their own database, `akshara_test`. Don't point them at real
data. A browser end-to-end check is described in [e2e/README.md](e2e/README.md).

## <img src="docs/headers/h2-project-structure.svg" alt="PROJECT STRUCTURE" height="38">

```
backend/    FastAPI app, database migrations, background workers and tests
frontend/   React web app
infra/      Dockerfiles and nginx config
docs/       architecture plan and design decisions
e2e/        browser end-to-end check
```

## <img src="docs/headers/h2-license.svg" alt="LICENSE" height="38">

MIT. See [LICENSE](LICENSE).
