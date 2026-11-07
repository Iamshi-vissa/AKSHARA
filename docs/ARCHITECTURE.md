# AKSHARA — System Architecture & Implementation Plan

> **Intelligence Behind Every Document.**
>
> Status: **v0.2 — plan approved. Phase 1 complete and verified (2026-11-07). Phases 2–9 not started.**

---

## Contents

0. [Decisions on ambiguous requirements](#0-decisions-on-ambiguous-requirements)
1. [System architecture](#1-system-architecture)
2. [Project directory structure](#2-project-directory-structure)
3. [Database schema](#3-database-schema)
4. [Backend module breakdown](#4-backend-module-breakdown)
5. [Frontend pages and components](#5-frontend-pages-and-components)
6. [API endpoint specification](#6-api-endpoint-specification)
7. [Canonical document representation (ADM)](#7-canonical-document-representation-adm)
8. [UDSE rule schema](#8-udse-rule-schema)
9. [Phase-by-phase implementation plan](#9-phase-by-phase-implementation-plan)
10. [Technical risks and mitigations](#10-technical-risks-and-mitigations)

---

## 0. Decisions on ambiguous requirements

The brief leaves these points open. Each has a safe default. Any of them can be changed before Phase 1 starts.

| # | Ambiguity | Default chosen | Why |
|---|-----------|----------------|-----|
| D1 | **Deployment shape.** Microservices or a monolith? | **Modular monolith** (one FastAPI app with strict internal module boundaries) plus **Celery workers** that run the same codebase. | It's one product with one team. Module boundaries are enforced in code (import rules), so we can split services out later without paying the cost of distributed systems now. |
| D2 | **Authentication.** Self-hosted or external IdP? | Self-hosted email + password (Argon2id), a short-lived JWT access token (15 min), and a **rotating refresh token** in an httpOnly, SameSite=Strict cookie. OIDC/SSO comes later behind the same `AuthProvider` interface. | It works offline and in development with no external accounts, and it doesn't block institutional SSO later. |
| D3 | **Tenancy.** Users, teams or organisations? | **User-level isolation now.** Every owned row has `owner_id`. A `workspace_id` column is reserved (nullable) for future team sharing. | Matches "user-level data isolation" without designing team permissions we don't need yet. |
| D4 | **Where binary files live.** | Behind a `BlobStorage` interface: **local filesystem** in development, **S3-compatible** (MinIO / S3) in production. Blobs are content-addressed (SHA-256) and **immutable**. | This is how "never overwrite originals" is enforced structurally. |
| D5 | **Editing PDFs.** PDF is a layout format, not an editable structure. | PDFs can be **inspected, validated and reported on**. Automatic corrections to a PDF are **not applied in place**. Instead the user gets an opt-in "Rebuild as DOCX" path, clearly labelled as lossy. | Rewriting PDF content streams silently corrupts layout. Being honest beats a fake fix. |
| D6 | **How DOCX/PPTX exports keep fidelity.** | **Patch-based export.** Corrections become operations applied to the *original OOXML package*, so XML we don't model is preserved. Only newly generated documents are written fresh from the ADM. | Regenerating a DOCX from an intermediate model loses unknown features (fields, content controls, custom XML). |
| D7 | **LanguageTool.** | A **self-hosted LanguageTool server** (Docker). We never call the public API by default. | Privacy: document text stays inside our infrastructure. |
| D8 | **Sending content to an LLM.** | LLM features stay **disabled until a provider is configured** through environment variables. A per-user consent flag (`allow_external_llm`) must be on before document text is sent to an external provider. Every call is logged (metadata and hashes only, never content). | Documents are private. The user decides. |
| D9 | **Vector store.** FAISS or pgvector? | **pgvector** | It avoids running a second store, it supports transactions and per-user filtering, and the scale we expect (guidelines, user references) is small. |
| D10 | **Built-in standards (IEEE/APA/MLA).** | Shipped as versioned YAML profiles. **Every rule cites its source** (official guide section/URL). Rules we can't source are left out, not guessed. Profiles are marked "built-in — verify against your venue/institution". | Follows "never invent formatting rules". The exact values are entered and reviewed in Phase 4. They aren't asserted in this document. |
| D11 | **Version history model.** | **Linear history per document** with a `parent_version_id` pointer, so branching is possible later. Every accepted change creates a new version. Nothing is ever mutated in place. | It's simple, auditable, and it supports undo and revert. |
| D12 | **Async jobs in tests.** | Tests run Celery in eager mode **only in unit tests**. Integration tests run a real worker through docker-compose. | Eager mode hides serialisation and concurrency bugs. |
| D13 | **Units.** | Internally **all lengths are points (pt, 1/72 in)**, stored as floats. Importers convert from EMU/twips/mm. The UI shows the user's preferred unit. | One canonical unit removes a whole class of comparison bugs. |
| D14 | **Indic and other non-Latin scripts.** (The product name suggests this audience.) | The ADM stores Unicode text and a `lang` attribute per run. Rendering containers ship the **Noto font family**. LanguageTool coverage for Indic languages is limited, so grammar features report "unsupported language" instead of producing nothing silently. | Fonts that are missing on the server cause false visual defects. |
| D15 | **Maximum upload.** | 50 MB file, 1,000 pages / 300 slides, 200 MB of decompressed OOXML. All configurable. | Guards against oversized files and zip bombs. |

---

## 1. System architecture

### 1.1 Context

```
                 ┌──────────────────────────────────────────────┐
  Browser  ───►  │  Frontend (React + TS + Vite + Tailwind)     │
                 └───────────────┬──────────────────────────────┘
                                 │ HTTPS  /api/v1  (JSON, SSE for job progress)
                 ┌───────────────▼──────────────────────────────┐
                 │  API (FastAPI, Pydantic v2)                  │
                 │  routers → application services → domain     │
                 └──┬──────────┬───────────┬──────────┬─────────┘
                    │          │           │          │
             ┌──────▼───┐ ┌────▼────┐ ┌────▼────┐ ┌───▼─────────────┐
             │PostgreSQL│ │  Redis  │ │  Blob   │ │ External (opt.) │
             │+pgvector │ │(broker, │ │ storage │ │ LLM provider    │
             └──────▲───┘ │ cache,  │ │(FS / S3)│ │ Crossref/OpenAlex│
                    │     │ rate-lim)│ └────▲────┘ └───▲─────────────┘
                    │     └────┬────┘      │          │
                 ┌──┴──────────▼───────────┴──────────┴─────────┐
                 │  Celery workers (same codebase)              │
                 │  queues: parse · render · inspect · llm ·    │
                 │          export · research                   │
                 │  ┌────────────────┐  ┌────────────────────┐  │
                 │  │LibreOffice     │  │LanguageTool server │  │
                 │  │headless (sandbx)│  │(self-hosted)       │  │
                 │  └────────────────┘  └────────────────────┘  │
                 └──────────────────────────────────────────────┘
```

### 1.2 Layering (inside the backend)

```
api/            HTTP only: routing, auth dependencies, request/response DTOs
  │
services/       Application use-cases: orchestrate, enforce ownership, start jobs, write audit
  │
domain/         PURE logic, no I/O: ADM model, inspection checks, UDSE rule engine,
  │             correction planner, scoring. Fully unit-testable.
  │
adapters/       I/O at the edges: importers/exporters (docx/pdf/pptx), renderer
                (LibreOffice, PyMuPDF), storage, LLM providers, LanguageTool,
                Crossref/OpenAlex, embeddings
```

Rules (checked in CI with `import-linter`):
- `domain` imports nothing from `api`, `services`, `adapters` or `db`.
- `adapters` never import `services`.
- Format-specific code exists **only** in `adapters/formats/<fmt>`. Every other module works on the ADM.

### 1.3 The central pipeline

```
Upload ─► Validate ─► Store original (immutable blob, sha256)
             │
             ▼
        [parse job]   importer(fmt) ─► ADM v1  (+ extracted assets)
             │
             ▼
        [render job]  LibreOffice → PDF → PyMuPDF → page PNGs + layout boxes
             │
             ▼
   ┌─────────┴───────────────────────────────────────────┐
   │ Inspection engine   (structure, formatting, layout) │──► Findings
   │ UDSE validator      (rules from standard profile)   │──► Compliance report
   │ Visual engine       (render-based checks)           │──► Visual findings
   └─────────┬───────────────────────────────────────────┘
             ▼
     Correction planner ─► ChangeSet (proposals, each linked to finding/rule)
             │                  ▲ user accepts / rejects each proposal
             ▼                  │
     Apply accepted ops ─► ADM v(n+1) + patched file ─► re-validate ─► new report
```

**Key invariants**
1. **Originals are immutable.** Blobs are write-once and content-addressed. No code path calls `delete`/`overwrite` on an `original` blob.
2. **Nothing changes without a ChangeSet.** AI edits, grammar fixes and auto-corrections all produce *proposals*. Only `POST /changesets/{id}/apply`, with explicitly accepted proposals, creates a new version.
3. **Deterministic over generative.** A hard constraint is checked by code. An LLM may *suggest* soft improvements and may *extract* rules, but an extracted rule must carry a verbatim quote that exists in the source text (see §8.5).
4. **Provenance everywhere.** ADM nodes carry their source location. Findings carry node IDs and page/bbox. Generated text carries `origin: generated`. References carry a verification status.
5. **No fake results.** If a check can't run (for example, the renderer isn't available or the language isn't supported), the result is `status: "not_evaluated"` with a reason. It is never reported as a pass.

### 1.4 Logical components → code modules

| Component (brief §7) | Backend module | Runs in |
|---|---|---|
| Auth & user mgmt | `services/auth`, `core/security` | API |
| Document upload | `services/documents`, `adapters/storage`, `core/filesafety` | API |
| Document parser | `adapters/formats/{docx,pdf,pptx}/importer.py` | worker:parse |
| Canonical representation | `domain/adm` | everywhere |
| Document editor | `services/editing`, `domain/changes` | API + worker:llm |
| Content generation | `services/generation`, `adapters/llm` | worker:llm |
| Inspection engine | `domain/inspection` | worker:inspect |
| UDSE rule engine | `domain/udse`, `services/standards` | worker:inspect |
| Auto-correction | `domain/correction`, `services/corrections` | API + worker:export |
| Presentation generation | `services/presentations`, `adapters/formats/pptx/exporter.py` | worker:llm/export |
| Visual quality engine | `domain/visual`, `adapters/render` | worker:render |
| Research & citation | `domain/references`, `services/research`, `adapters/scholarly` | worker:research |
| Export service | `services/exports`, `adapters/formats/*/exporter.py` | worker:export |
| Version management | `services/versions` | API |
| Reporting | `domain/scoring`, `services/reports` | API |

---

## 2. Project directory structure

```
akshara/
├── README.md
├── .env.example                     # every setting documented; no real secrets
├── docker-compose.yml               # postgres, redis, minio, languagetool, api, worker, web
├── Makefile                         # dev, test, lint, migrate, fixtures
├── docs/
│   ├── ARCHITECTURE.md              # this file
│   ├── adr/                         # Architecture Decision Records (0001-modular-monolith.md …)
│   ├── adm-spec.md                  # canonical model reference (generated from schema)
│   ├── udse-rule-spec.md
│   └── standards-sources.md         # citation for every built-in rule
├── infra/
│   ├── docker/
│   │   ├── api.Dockerfile
│   │   ├── worker.Dockerfile        # + LibreOffice, Noto fonts, non-root, no network for render
│   │   └── web.Dockerfile
│   └── nginx/                       # prod reverse proxy, upload size limits, security headers
├── backend/
│   ├── pyproject.toml               # deps pinned; ruff, mypy, pytest, import-linter config
│   ├── alembic.ini
│   ├── migrations/versions/
│   ├── app/
│   │   ├── main.py                  # app factory, middleware, router mount
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings, env vars only
│   │   │   ├── security.py          # hashing, JWT, token rotation
│   │   │   ├── filesafety.py        # magic-byte sniffing, zip-bomb guard, macro stripping
│   │   │   ├── logging.py           # structured JSON logs, request IDs, PII redaction
│   │   │   ├── errors.py            # error envelope + exception handlers
│   │   │   └── ratelimit.py
│   │   ├── db/
│   │   │   ├── base.py  session.py
│   │   │   └── models/              # SQLAlchemy 2.0 models, one file per aggregate
│   │   │       ├── user.py document.py job.py inspection.py standard.py
│   │   │       ├── changeset.py reference.py generation.py audit.py
│   │   ├── api/
│   │   │   ├── deps.py              # current_user, pagination, ownership loaders
│   │   │   └── v1/
│   │   │       ├── auth.py documents.py versions.py jobs.py inspections.py
│   │   │       ├── standards.py validations.py changesets.py editing.py
│   │   │       ├── generation.py presentations.py exports.py references.py reports.py
│   │   ├── schemas/                 # Pydantic API DTOs (separate from ADM)
│   │   ├── services/                # one package per use-case area (see §4)
│   │   ├── domain/
│   │   │   ├── adm/                 # nodes.py, styles.py, ids.py, traverse.py, diff.py, ops.py
│   │   │   ├── inspection/          # checks/*.py, registry.py, severity.py
│   │   │   ├── udse/                # schema.py, selectors.py, operators.py, engine.py, extraction_validate.py
│   │   │   ├── correction/          # planner.py, fixers/*.py
│   │   │   ├── changes/             # changeset model, tracked-change semantics
│   │   │   ├── visual/              # overflow.py, blank_page.py, alignment.py, balance.py
│   │   │   ├── references/          # parse.py, normalize.py, styles (CSL), consistency.py
│   │   │   └── scoring/             # quality score model
│   │   ├── adapters/
│   │   │   ├── formats/
│   │   │   │   ├── base.py          # Importer / Exporter / Patcher protocols + registry
│   │   │   │   ├── docx/  importer.py exporter.py patcher.py
│   │   │   │   ├── pdf/   importer.py exporter.py (ReportLab)
│   │   │   │   └── pptx/  importer.py exporter.py patcher.py
│   │   │   ├── render/              # libreoffice.py (sandboxed subprocess), rasterize.py (PyMuPDF)
│   │   │   ├── storage/             # base.py, local.py, s3.py
│   │   │   ├── llm/                 # base.py, anthropic.py, openai.py, ollama.py, registry.py
│   │   │   ├── embeddings/
│   │   │   ├── languagetool.py
│   │   │   └── scholarly/           # crossref.py, openalex.py, doi.py, url_check.py
│   │   └── workers/
│   │       ├── celery_app.py
│   │       └── tasks/  parse.py render.py inspect.py validate.py llm.py export.py research.py
│   ├── standards/builtin/           # ieee.yaml apa7.yaml mla9.yaml (sourced, versioned)
│   └── tests/
│       ├── conftest.py
│       ├── unit/                    # domain logic: no DB, no network
│       ├── integration/             # API + DB + worker + LibreOffice
│       ├── e2e/                     # Playwright against full stack
│       └── fixtures/
│           ├── build_fixtures.py    # generates sample docs PROGRAMMATICALLY
│           ├── manifest.yaml        # each fixture → its known, expected violations
│           └── documents/           # generated output (git-ignored) + a few real samples
└── frontend/
    ├── package.json  vite.config.ts  tailwind.config.ts  tsconfig.json
    ├── src/
    │   ├── main.tsx  App.tsx  router.tsx
    │   ├── api/                     # typed client generated from OpenAPI (openapi-typescript)
    │   ├── lib/                     # auth store, query client, formatting, units
    │   ├── components/ui/           # Button, Input, Dialog, Tabs, Badge, Table, Toast, Skeleton…
    │   ├── components/layout/       # AppShell, Sidebar, TopBar, PageHeader
    │   ├── features/
    │   │   ├── auth/  documents/  workspace/  inspection/  standards/
    │   │   ├── changes/  generation/  presentations/  quality/  references/
    │   └── pages/                   # route-level components (see §5)
    └── tests/                       # Vitest + Testing Library
```

**Why fixtures are generated programmatically:** `build_fixtures.py` uses python-docx/python-pptx/ReportLab to build documents with *known, deliberate* violations (for example, "Heading 2 directly after Heading 0", "left margin 0.5 in", "Figure 3 missing caption"). `manifest.yaml` lists the findings each one must produce. That gives the UDSE and the inspection engine exact, reproducible ground truth.

---

## 3. Database schema

PostgreSQL 16 with the `pgvector`, `citext` and `pgcrypto` extensions. All primary keys are `uuid` (UUIDv7, sortable by time). All timestamps are `timestamptz`. Every user-owned table has `owner_id` and is accessed only through services that filter on it.

### 3.1 Identity

```
users
  id uuid PK
  email citext UNIQUE NOT NULL
  password_hash text NOT NULL              -- argon2id
  display_name text
  is_active bool DEFAULT true
  is_admin bool DEFAULT false
  allow_external_llm bool DEFAULT false    -- D8 consent
  preferred_unit text DEFAULT 'pt'         -- pt|mm|in
  created_at, updated_at

refresh_tokens
  id uuid PK
  user_id uuid FK users ON DELETE CASCADE
  token_hash text UNIQUE NOT NULL          -- sha256 of opaque token; raw never stored
  family_id uuid NOT NULL                  -- rotation family; reuse ⇒ revoke family
  expires_at, revoked_at, created_at, user_agent, ip
```

### 3.2 Documents, blobs, versions

```
blobs                                      -- immutable binary objects
  sha256 char(64) PK
  size_bytes bigint, mime_type text
  storage_key text NOT NULL
  created_at

documents
  id uuid PK
  owner_id uuid FK users  NOT NULL
  workspace_id uuid NULL                   -- reserved (D3)
  title text NOT NULL
  kind text NOT NULL                       -- docx|pdf|pptx
  origin text NOT NULL                     -- uploaded|generated
  current_version_id uuid FK document_versions NULL
  applied_standard_version_id uuid FK standard_versions NULL
  status text NOT NULL                     -- uploading|processing|ready|failed
  deleted_at timestamptz NULL              -- soft delete; blobs retained per policy
  created_at, updated_at
  INDEX (owner_id, updated_at DESC)

document_versions
  id uuid PK
  document_id uuid FK documents NOT NULL
  number int NOT NULL                      -- 1,2,3… UNIQUE(document_id, number)
  parent_version_id uuid FK document_versions NULL
  source_blob sha256 FK blobs NOT NULL     -- the file for this version (v1 = original upload)
  adm_blob sha256 FK blobs NULL            -- gzipped ADM JSON
  adm_schema_version text                  -- e.g. "1.0"
  created_by text NOT NULL                 -- upload|changeset|generation|rebuild
  changeset_id uuid FK changesets NULL
  summary jsonb                            -- page_count, word_count, node counts
  created_at

document_assets                            -- images/media extracted at parse
  id uuid PK, version_id FK, node_id text, blob sha256 FK, mime_type, width_px, height_px

render_pages                               -- output of render job
  id uuid PK, version_id FK, page_index int, image_blob sha256 FK,
  width_pt, height_pt, layout_blob sha256 FK   -- text/box geometry JSON from PyMuPDF
  UNIQUE(version_id, page_index)
```

### 3.3 Jobs

```
jobs
  id uuid PK
  owner_id uuid FK users
  type text                                -- parse|render|inspect|validate|edit|generate|export|research|extract_standard
  status text                              -- queued|running|succeeded|failed|cancelled
  progress real DEFAULT 0
  subject_type text, subject_id uuid       -- e.g. ('document_version', …)
  params jsonb, result jsonb
  error_code text, error_message text      -- user-safe message; stack trace only in logs
  celery_task_id text
  created_at, started_at, finished_at
  INDEX (owner_id, created_at DESC)
```

### 3.4 Inspection & findings

```
inspection_runs
  id uuid PK, owner_id, version_id FK
  kind text                                -- structural|formatting|visual|udse|full
  standard_version_id uuid FK NULL         -- set when kind=udse
  engine_version text                      -- for reproducibility
  status text, started_at, finished_at
  stats jsonb                              -- counts per severity, not_evaluated counts

findings
  id uuid PK
  run_id uuid FK inspection_runs ON DELETE CASCADE
  code text NOT NULL                       -- e.g. STRUCT.HEADING_SKIP, UDSE.MARGIN.LEFT
  category text                            -- structure|typography|page|references|figures_tables|layout|content
  severity text                            -- critical|high|medium|low|info
  status text                              -- open|proposed|fixed|dismissed|not_evaluated
  rule_id text NULL                        -- UDSE rule id when applicable
  constraint_kind text NULL                -- hard|soft
  node_ids text[]                          -- ADM node ids
  page_index int NULL, bbox real[4] NULL   -- location on rendered page
  location_label text                      -- human: "Section 2.1, paragraph 3 (page 4)"
  message text                             -- what is wrong
  explanation text                         -- why it matters / which rule
  expected jsonb, actual jsonb             -- machine-readable comparison
  recommendation text
  fix_available bool
  detector text                            -- deterministic|visual|llm
  confidence real                          -- 1.0 for deterministic
  INDEX (run_id, severity)

compliance_reports
  id uuid PK, owner_id, version_id FK, standard_version_id FK, run_id FK
  scores jsonb                             -- see §4 scoring
  hard_pass int, hard_fail int, soft_pass int, soft_fail int, not_evaluated int
  report_blob sha256 FK NULL               -- rendered PDF/HTML report
  created_at
```

### 3.5 Standards (UDSE)

```
standards
  id uuid PK
  owner_id uuid NULL                       -- NULL = built-in
  slug text, name text, description text
  family text                              -- ieee|apa|mla|institutional|corporate|custom
  is_builtin bool
  created_at
  UNIQUE(owner_id, slug)

standard_versions                          -- immutable once published
  id uuid PK, standard_id FK
  version text                             -- semver
  parent_standard_version_id uuid NULL     -- inheritance ("extends IEEE")
  status text                              -- draft|published|archived
  rules jsonb NOT NULL                     -- array of UDSE rules (§8), validated by schema
  rules_hash char(64)                      -- reproducibility
  created_at, published_at

guideline_sources                          -- uploaded guideline / sample docs
  id uuid PK, owner_id, standard_id FK
  document_id uuid FK documents            -- reuses the document pipeline
  role text                                -- guideline|sample
  created_at

rule_extraction_candidates                 -- review queue for Custom Standard Builder
  id uuid PK, standard_id FK, source_id FK guideline_sources
  candidate jsonb                          -- proposed rule
  evidence_quote text, evidence_page int, evidence_node_id text
  evidence_verified bool                   -- quote found verbatim in source? (§8.5)
  method text                              -- pattern|llm|sample_inference
  review_status text                       -- pending|accepted|edited|rejected
  reviewed_at

guideline_chunks                           -- RAG over guidelines
  id uuid PK, source_id FK, owner_id, text text, page int, embedding vector(<dim>)
```

### 3.6 Changes and versioning

```
changesets
  id uuid PK, owner_id, document_id FK
  base_version_id uuid FK NOT NULL         -- proposals computed against this
  source text                              -- autocorrect|grammar|ai_edit|manual
  status text                              -- open|applied|discarded|stale
  result_version_id uuid FK NULL
  created_at, applied_at

change_proposals
  id uuid PK, changeset_id FK ON DELETE CASCADE
  ordinal int
  op jsonb NOT NULL                        -- ADM operation (§7.6)
  finding_id uuid FK findings NULL
  rule_id text NULL
  rationale text
  before_preview text, after_preview text  -- for diff UI
  risk text                                -- formatting_only|content_change|structural
  decision text DEFAULT 'pending'          -- pending|accepted|rejected
  decided_at
```

Undo/redo inside an editing session is client-side, over the proposal decisions. Cross-session undo means **reverting to an earlier version**, which creates a new version copied from it. History is never rewritten.

### 3.7 References

```
references
  id uuid PK, owner_id, document_id FK NULL, version_id FK NULL
  node_id text NULL                        -- bibliography entry in ADM
  raw_text text
  csl_json jsonb                           -- normalized (CSL-JSON)
  provenance text                          -- user_provided|extracted|suggested
  verification_status text                 -- unverified|verified|mismatch|not_found|error
  verified_against text NULL               -- crossref|openalex|url
  verification_evidence jsonb              -- matched record id, similarity scores
  verified_at
  INDEX (owner_id, document_id)
```

### 3.8 Generation, LLM audit, general audit

```
generation_sessions
  id uuid PK, owner_id, document_id FK NULL
  kind text                                -- research_paper|report|proposal|letter|…|presentation
  brief jsonb                              -- topic, tone, word target, instructions
  outline jsonb                            -- editable outline
  status text, created_at

llm_calls                                  -- metadata only, never prompts/content
  id uuid PK, owner_id, job_id FK NULL
  provider text, model text, purpose text
  input_tokens int, output_tokens int, latency_ms int
  prompt_sha256 char(64), status text, created_at

audit_events
  id bigserial PK, owner_id, actor_id, action text, subject_type, subject_id,
  metadata jsonb, ip inet, created_at
```

---

## 4. Backend module breakdown

| Module | Responsibility | Key interfaces |
|---|---|---|
| `core.config` | Typed settings from env (`AKSHARA_*`). Fails fast if a required secret is missing. | `Settings` |
| `core.security` | Argon2id hashing, JWT issue/verify, refresh rotation with reuse detection. | `hash_password`, `issue_tokens`, `rotate_refresh` |
| `core.filesafety` | Magic-byte sniffing (does the extension match the content?), OOXML zip inspection (entry count, ratio, total size, path traversal), **macro removal** (`vbaProject.bin`, `.docm/.pptm` rejected or stripped), XXE-safe XML parsing (`defusedxml`), PDF JavaScript/launch-action detection (flagged, never executed). | `validate_upload(stream) -> SafeFile` |
| `services.auth` | Register, login, refresh, logout, me. | |
| `services.documents` | Upload → blob → document → v1 → start parse+render. List, get, rename, soft delete. Every query is scoped by `owner_id`. | |
| `services.versions` | List, get ADM, download file, revert (creates a new version), diff two versions (ADM diff). | |
| `services.jobs` | Create and track jobs, SSE progress stream, cancel. | |
| `adapters.formats.*` | **Importers:** file → ADM (with fidelity flags). **Exporters:** ADM → new file. **Patchers:** original file + ops → new file (DOCX/PPTX). | `Importer.parse(path) -> AdmDocument`, `Patcher.apply(src, ops) -> bytes` |
| `adapters.render` | LibreOffice headless conversion to PDF (subprocess with timeout, per-job profile dir, no network, rlimits), PyMuPDF rasterisation (PNG at 110 dpi for preview, 200 dpi for visual analysis), text box geometry extraction. | `render(version) -> RenderResult` |
| `domain.adm` | The model (§7), traversal, stable IDs, diff, operations. | |
| `domain.inspection` | Registry of independent checks. Each check declares `code`, `category`, default `severity`, required inputs (ADM only, or ADM + render). The engine runs checks and gathers findings. A check that's missing its inputs returns `not_evaluated`. | `Check.run(ctx) -> list[Finding]` |
| `domain.udse` | Rule schema, selector resolution, operator library, deterministic evaluator, soft-rule LLM evaluation (rubric-constrained), check that extraction evidence is real. | `evaluate(adm, render, rules) -> list[RuleResult]` |
| `domain.correction` | Maps failed rules/findings → fixers → ADM ops. Each fixer is deterministic and declares its `risk`. | `plan(findings) -> list[Proposal]` |
| `domain.changes` | ChangeSet semantics: rebase detection (is the base version stale?), conflict detection for overlapping ops. | |
| `services.corrections` | Build a ChangeSet from findings, record decisions, apply (ops → ADM v+1 + patched file) → re-render → re-validate → compliance report. | |
| `services.editing` | Grammar/spelling (LanguageTool) and AI rewrite operations (paraphrase, summarise, expand, tone, clarity, academic/professional) at paragraph or section scope. **Output is always a ChangeSet**, with a meaning-preservation check (a second LLM pass) shown as a warning, never as a block. | |
| `services.generation` | Brief → outline → section-by-section drafts → ADM → DOCX/PDF. Generated nodes are tagged `origin=generated`. Citations can only point at `references` rows. With no verified references, the text uses visible `[citation needed]` placeholders. | |
| `services.presentations` | Brief/document → slide outline → slides (title, bullets, notes, image slots) → PPTX via theme templates. Validation through the visual engine. | |
| `domain.visual` | Checks over render output: text-box overflow beyond page/slide bounds, clipped text (ADM text vs. rendered text diff), blank pages, table wider than its text block, images over margins, alignment deviation within a slide, slide density, page-break orphans/widows. | |
| `domain.references` + `services.research` | Parse references into CSL-JSON, consistency checks (style, ordering, citation↔bibliography matching), DOI syntax and resolution (Crossref), metadata comparison, URL liveness (HEAD with SSRF protection), source discovery (OpenAlex/Crossref search). Discovery results are `suggested` until the user accepts them. | |
| `domain.scoring` | Transparent scoring (below). | |
| `services.reports` | Build quality dashboard data and exportable PDF/HTML reports (ReportLab). | |
| `adapters.llm` | `LLMProvider` protocol: `complete(messages, *, response_schema, max_tokens, temperature)`. Providers: Anthropic, OpenAI-compatible, Ollama. The model is chosen by `AKSHARA_LLM_PROVIDER` / `AKSHARA_LLM_MODEL`. Structured output is validated with Pydantic, with up to 2 retries, then a hard failure (never a fabricated fallback). | |

**Scoring model (transparent, documented in reports)**

- Dimensions: `formatting`, `structure`, `content`, `visual`, and `references`.
- `dimension_score = 100 × (1 − Σ w(sev)·count / normaliser)`, with weights critical 25, high 10, medium 4, low 1, info 0, and the result clamped to the range [0, 100].
- **Any failed hard constraint caps the overall compliance score at 69**, and the report reads "Not compliant". A document can't look compliant while it breaks a mandatory rule.
- Checks marked `not_evaluated` are excluded from the score and shown separately as reduced coverage.
- `content` is LLM-assessed, so it is always shown with a "model-assessed" label and is never mixed into the compliance score.

---

## 5. Frontend pages and components

**Stack:** React 18, TypeScript (strict), Vite, Tailwind, React Router, TanStack Query (server state), Zustand (small client state: auth session, workspace UI). A typed API client is generated from FastAPI's OpenAPI spec. Rich-text editing (Phase 5) uses TipTap/ProseMirror for paragraph editing only. Tracked changes are *our* ChangeSet model rendered as decorations, not an editor plugin, so the server stays the source of truth.

**Visual language.** "Precision" is expressed through a neutral palette with one accent colour (deep indigo), the Inter typeface for the UI and Source Serif for document previews, an 8 px spacing grid, and fixed severity colours (critical red, high orange, medium amber, low blue, info slate) always paired with an icon and a label, never colour alone. The target is WCAG 2.1 AA, with full keyboard navigation and a 1280-px-first layout that collapses side panels into drawers below 1024 px.

### 5.1 Routes

| Route | Page | Contents |
|---|---|---|
| `/login`, `/register` | Auth | Forms, errors, password rules |
| `/` | **Dashboard** | Quick actions (Create · Inspect · Edit · Apply standard · Generate presentation), recent documents table, recent reports, running jobs |
| `/documents` | Library | Search/filter by type and status, upload drop zone |
| `/documents/:id` | **Document workspace** | 3-pane layout (below) |
| `/documents/:id/versions` | Version history | Timeline, diff between any two versions, revert, download |
| `/documents/:id/inspect/:runId` | Inspection report | Findings grouped by severity/category, page jump |
| `/documents/:id/quality` | **Quality dashboard** | Overall score, per-dimension scores, critical issues, recommended corrections, coverage notes |
| `/standards` | **Standard engine** | Built-in and custom standards, versions |
| `/standards/:id` | Standard detail | Rules table (filter hard/soft, category), rule editor, publish version |
| `/standards/new` | **Custom Standard Builder** | Wizard: upload guidelines/samples → extraction job → review candidates (with evidence quote and page thumbnail) → edit → save/publish |
| `/create` | Document creation | Type picker → brief form (topic, instructions, tone, word target, citation style) → outline editor → section generation → review → export |
| `/presentations/new` | Presentation generator | Brief or "from document" → outline → theme/layout → generate → slide validation |
| `/references` | Reference manager | Library, verification statuses, import (BibTeX/RIS/DOI) |
| `/settings` | Settings | Profile, units, LLM consent, sessions |

### 5.2 Document workspace layout

```
┌──────────────┬──────────────────────────────────┬────────────────────┐
│ Structure    │  Preview / Editor                │  Side panel (tabs) │
│ navigator    │  ┌─ toggle: Page view | Text ─┐  │  • Compliance      │
│ (outline     │  │ page PNGs with finding     │  │  • Findings        │
│  tree from   │  │ overlays (bbox highlights) │  │  • Changes         │
│  ADM)        │  │  — or —                    │  │  • Assistant       │
│              │  │ ADM text view (editable)   │  │  • Formatting      │
│              │  └────────────────────────────┘  │  • References      │
└──────────────┴──────────────────────────────────┴────────────────────┘
 Top bar: title · version selector · applied standard · Inspect · Validate · Export
```

### 5.3 Component inventory

- **ui/** (in-house, Tailwind; no heavy component library): `Button`, `IconButton`, `Input`, `Textarea`, `Select`, `Checkbox`, `Dialog`, `Drawer`, `Tabs`, `Tooltip`, `Badge`, `SeverityBadge`, `ScoreRing`, `ProgressBar`, `Table`, `EmptyState`, `Skeleton`, `Toast`, `FileDropzone`.
- **features/documents:** `DocumentTable`, `UploadDialog` (client-side type/size pre-check, upload progress), `JobProgress` (SSE).
- **features/workspace:** `StructureTree`, `PageViewer` (lazy-loaded page images, zoom, `FindingOverlay`), `AdmTextView`, `VersionSelector`, `WorkspaceTopBar`.
- **features/inspection:** `FindingList`, `FindingCard` (location, explanation, recommendation, "Propose fix"), `SeverityFilter`.
- **features/changes:** `ChangeSetPanel`, `ProposalItem` (inline diff, accept/reject), `BulkDecisionBar` (accept all formatting-only), `ApplyChangesDialog` (summary → apply → revalidation result), `DiffView`.
- **features/standards:** `StandardList`, `RuleTable`, `RuleEditor` (schema-driven form with unit input), `ExtractionReview` (candidate + evidence quote + source page), `StandardVersionBadge`.
- **features/quality:** `QualityScoreCard`, `DimensionBreakdown`, `CriticalIssuesList`, `CoverageNotice`.
- **features/generation:** `BriefForm`, `OutlineEditor` (drag to reorder), `SectionGenerator`, `GeneratedContentBadge`.
- **features/presentations:** `SlideOutline`, `ThemePicker`, `SlideThumbGrid`, `SlideIssueList`.
- **features/references:** `ReferenceTable`, `VerificationBadge` (verified / unverified / user-provided / suggested — four visually distinct states), `ImportReferencesDialog`.

**Honesty in the UI.** Every result shown comes from an API response. Pending work shows skeletons and job progress, never placeholder results. Results marked `not_evaluated` are shown as such.

---

## 6. API endpoint specification

Base path: `/api/v1`. JSON throughout. Authenticated with `Authorization: Bearer <access>`. Refresh happens through the httpOnly cookie on `/auth/refresh`. Errors use one envelope:

```json
{ "error": { "code": "DOCUMENT_NOT_FOUND", "message": "…", "request_id": "…", "details": {} } }
```

Lists use cursor pagination (`?cursor=&limit=`). Long operations return `202 { "job_id" }`. Progress is available from `GET /jobs/{id}` or the SSE stream `GET /jobs/{id}/events`. Resources owned by another user return **404** (not 403), so their existence isn't leaked.

### Auth
| Method | Path | Body / Notes | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, display_name}` | `201 User` |
| POST | `/auth/login` | `{email, password}` (rate-limited) | `{access_token, expires_in}` + refresh cookie |
| POST | `/auth/refresh` | cookie | new access + rotated cookie |
| POST | `/auth/logout` | cookie | `204`, family revoked |
| GET | `/auth/me` | | `User` |
| PATCH | `/auth/me` | `{display_name, preferred_unit, allow_external_llm}` | `User` |

### Documents & versions
| Method | Path | Notes |
|---|---|---|
| POST | `/documents` | multipart `file`, optional `title`. Validated → `202 {document, job_id}` (parse + render) |
| GET | `/documents` | `?kind=&status=&q=` |
| GET | `/documents/{id}` | includes current version summary |
| PATCH | `/documents/{id}` | rename, set applied standard |
| DELETE | `/documents/{id}` | soft delete |
| GET | `/documents/{id}/versions` | |
| GET | `/versions/{vid}` | metadata + summary |
| GET | `/versions/{vid}/adm` | ADM JSON (`?include=outline` for the tree only) |
| GET | `/versions/{vid}/pages` | page list with dimensions |
| GET | `/versions/{vid}/pages/{n}/image` | PNG (`?dpi=`) |
| GET | `/versions/{vid}/file` | download this version's file |
| POST | `/documents/{id}/revert` | `{version_id}` → new version |
| GET | `/documents/{id}/diff?from=&to=` | ADM diff |

### Jobs
| GET | `/jobs/{id}` · GET `/jobs/{id}/events` (SSE) · POST `/jobs/{id}/cancel` · GET `/jobs?status=` |
|---|---|

### Inspection & validation
| Method | Path | Notes |
|---|---|---|
| POST | `/versions/{vid}/inspections` | `{kinds: ["structural","formatting","visual"]}` → `202 job` |
| GET | `/inspections/{run_id}` | run + stats |
| GET | `/inspections/{run_id}/findings` | `?severity=&category=&status=` |
| PATCH | `/findings/{fid}` | `{status: "dismissed", reason}` |
| POST | `/versions/{vid}/validations` | `{standard_version_id}` → `202 job` → compliance report |
| GET | `/compliance-reports/{id}` | scores, rule results |
| GET | `/compliance-reports/{id}/export?format=pdf\|html\|json` | |
| GET | `/documents/{id}/quality` | latest per-dimension scores for the quality dashboard |

### Standards (UDSE)
| Method | Path | Notes |
|---|---|---|
| GET | `/standards` | built-in + own |
| POST | `/standards` | `{name, family, extends_standard_version_id?}` |
| GET | `/standards/{id}` · PATCH · DELETE (own only) | |
| GET | `/standards/{id}/versions` | |
| POST | `/standards/{id}/versions` | create draft (copy of latest) |
| GET/PUT | `/standard-versions/{svid}/rules` | PUT validates against the rule JSON Schema; only allowed on drafts |
| POST | `/standard-versions/{svid}/publish` | makes it immutable |
| GET | `/udse/rule-schema` | JSON Schema for the rule editor |
| POST | `/standards/{id}/sources` | attach an uploaded document as `guideline` or `sample` |
| POST | `/standards/{id}/extract` | `202 job` → candidates |
| GET | `/standards/{id}/candidates` | review queue |
| PATCH | `/candidates/{cid}` | accept / edit / reject |

### Changes, editing, correction
| Method | Path | Notes |
|---|---|---|
| POST | `/documents/{id}/changesets` | `{source:"autocorrect", finding_ids[]}` or `{source:"grammar", scope}` or `{source:"ai_edit", operation, scope:{node_ids[]}, params}` → `202 job` (LLM-backed) or `201` |
| GET | `/changesets/{csid}` | proposals with previews |
| PATCH | `/changesets/{csid}/proposals/{pid}` | `{decision: accepted\|rejected\|pending}` |
| POST | `/changesets/{csid}/decisions` | bulk `{accept:[...], reject:[...]}` |
| POST | `/changesets/{csid}/apply` | requires ≥1 accepted. → `202 job`: new version → re-render → revalidate. `409` if the base is stale |
| POST | `/changesets/{csid}/discard` | |

AI edit `operation` values: `grammar`, `spelling`, `restructure`, `paraphrase`, `summarize`, `expand`, `tone`, `clarity`, `academic`, `professional`.

### Generation & presentations
| Method | Path | Notes |
|---|---|---|
| POST | `/generation/sessions` | `{kind, topic, instructions, tone, word_target, citation_style, reference_ids[]}` |
| POST | `/generation/sessions/{gid}/outline` | `202 job` |
| PUT | `/generation/sessions/{gid}/outline` | user edits |
| POST | `/generation/sessions/{gid}/sections/{sid}/generate` | `202 job` |
| POST | `/generation/sessions/{gid}/finalize` | creates a document + v1 |
| POST | `/presentations` | `{brief \| source_document_id, theme, slide_count, audience}` → `202 job` |
| GET | `/presentation-themes` | |

### Export
| POST | `/versions/{vid}/exports` `{format: docx\|pdf\|pptx}` → `202 job` · GET `/exports/{id}/file` |
|---|---|

### References & research
| Method | Path | Notes |
|---|---|---|
| GET/POST | `/references` | create from `{doi}` \| `{raw_text}` \| `{csl_json}` \| BibTeX/RIS upload |
| POST | `/references/{rid}/verify` | `202 job` |
| POST | `/versions/{vid}/references/check` | extract + consistency + verification report |
| POST | `/research/search` | `{query, filters}` → results labelled `suggested` |
| POST | `/references/format` | `{reference_ids[], style}` → formatted strings (CSL) |

### System
`GET /health` (liveness) · `GET /ready` (DB, Redis, storage, LibreOffice, LanguageTool and LLM status, each reported separately) · `GET /capabilities` (which optional features are configured; the UI uses it to hide or disable features honestly).

---

## 7. Canonical document representation (ADM)

**ADM — the AKSHARA Document Model.** It is a JSON-serialisable tree, defined as Pydantic models and versioned (`adm_schema_version`). It's one representation for DOCX, PDF and PPTX: flow documents use `body`, presentations use `slides`.

### 7.1 Design principles

1. **Stable node IDs.** Each node has an `id` (short ULID) that persists across versions as long as the node exists. Findings, proposals and comments reference these IDs.
2. **Source anchors.** Each node records where it came from (`source`), so a patcher can find the exact OOXML element or PDF region again.
3. **Resolved and declared formatting.** We store the **declared style** (`style_ref`: "Heading 1") *and* the **effective formatting** after style inheritance is resolved. UDSE checks the effective values. Fixes prefer changing the style when that's safe.
4. **Fidelity flags.** Every formatting property has a fidelity of `exact` (read from the file), `inferred` (derived, e.g. heading level guessed from a PDF font size) or `unknown`. Hard rules over `inferred` values produce findings with reduced confidence. Over `unknown` values they produce `not_evaluated`.
5. **Origin.** `origin: original | edited | generated` per text-bearing node, to support "distinguish generated content".

### 7.2 Top level

```jsonc
{
  "adm_schema_version": "1.0",
  "doc_id": "…", "version_id": "…",
  "source_format": "docx",               // docx | pdf | pptx | generated
  "metadata": {
    "title": "…", "authors": ["…"], "subject": null, "keywords": [],
    "language": "en-US", "created": "…", "modified": "…",
    "page_count": 12, "word_count": 4210,
    "has_macros_removed": false, "has_tracked_changes": false, "has_comments": true
  },
  "page_setups": [                        // one per DOCX section / PDF page group
    { "id": "ps1",
      "paper": { "width_pt": 612, "height_pt": 792, "name": "Letter" },
      "orientation": "portrait",
      "margins_pt": { "top": 72, "bottom": 72, "left": 72, "right": 72, "gutter": 0 },
      "columns": { "count": 2, "gap_pt": 18 },
      "header_ids": ["h1"], "footer_ids": ["f1"],
      "page_numbering": { "format": "decimal", "start": 1, "position": "footer-center" },
      "fidelity": "exact" }
  ],
  "styles": { "Heading1": { "kind": "paragraph", "based_on": "Normal", "fmt": { … } }, … },
  "body": [ /* Block[] — flow docs */ ],
  "headers_footers": [ /* HeaderFooter[] */ ],
  "footnotes": [ /* Footnote[] */ ],
  "slides": [ /* Slide[] — pptx only */ ],
  "bibliography": { "node_id": "sec-refs", "entries": [ /* ReferenceEntry ids */ ] },
  "assets": [ { "id": "img1", "blob": "sha256…", "mime": "image/png", "px": [1200, 800], "dpi": 300 } ]
}
```

### 7.3 Node types

```jsonc
// Common to all nodes
{ "id": "n_01H…", "type": "...", "source": Source, "origin": "original" }

// Source anchor (one of)
{ "fmt": "docx", "part": "word/document.xml", "xpath": "/w:document/w:body/w:p[37]", "para_idx": 36 }
{ "fmt": "pdf",  "page": 4, "bbox": [72.0, 540.2, 540.0, 610.8], "block_idx": 12 }
{ "fmt": "pptx", "slide": 3, "shape_id": 5, "para_idx": 1 }

// Section — logical grouping created from heading hierarchy
{ "type": "section", "level": 1, "heading_id": "n_h1", "numbering": "2", "role": "methodology",
  "children": [Block…] }
// role ∈ title|abstract|keywords|introduction|related_work|methodology|results|discussion|
//        conclusion|references|appendix|acknowledgements|unknown  (classified; confidence stored)

// Heading
{ "type": "heading", "level": 2, "text": "2.1 Data Collection", "numbering": { "label": "2.1", "auto": true },
  "style_ref": "Heading2", "runs": [Run…], "fmt": ParaFmt, "level_fidelity": "exact" }

// Paragraph
{ "type": "paragraph", "role": "body",   // body|caption|list_item|quote|code|title|subtitle|author|affiliation|abstract|keywords
  "style_ref": "Normal", "runs": [Run…], "fmt": ParaFmt }

// Run (inline)
{ "text": "…", "fmt": RunFmt, "lang": "en-US",
  "marks": [ {"kind": "citation", "ref_ids": ["ref_3"]}, {"kind": "link", "href": "…"},
             {"kind": "xref", "target": "fig_2"}, {"kind": "footnote_ref", "target": "fn_1"} ] }

// RunFmt (effective) — each property: {value, fidelity}
{ "font_family": {"v":"Times New Roman","f":"exact"}, "size_pt": {"v":10,"f":"exact"},
  "bold": …, "italic": …, "underline": …, "color": "#000000", "superscript": false, "small_caps": false }

// ParaFmt (effective)
{ "alignment": "justify", "line_spacing": {"rule":"multiple","value":1.0},
  "space_before_pt": 0, "space_after_pt": 6, "indent_first_pt": 14.4, "indent_left_pt": 0, "indent_right_pt": 0,
  "keep_with_next": false, "page_break_before": false }

// List
{ "type": "list", "ordered": true, "numbering_format": "decimal", "items": [ { "type":"list_item", "level":0, "children":[Block…] } ] }

// Table
{ "type": "table", "rows": [ { "cells": [ { "children":[Block…], "col_span":1, "row_span":1, "is_header": true } ] } ],
  "col_widths_pt": [120, 200], "width_pt": 320, "caption_id": "n_cap7", "numbering": "II", "fmt": {…} }

// Figure
{ "type": "figure", "asset_id": "img1", "size_pt": [252, 168], "anchor": "inline|floating",
  "position": { "page": 5, "bbox": [...] }, "caption_id": "n_cap3", "numbering": "3", "alt_text": "…" }

// Caption
{ "type": "caption", "target_id": "fig_3", "target_kind": "figure|table|equation",
  "label": "Fig. 3.", "runs": [Run…], "position": "below|above" }

// Equation · CodeBlock · PageBreak · SectionBreak · TableOfContents · Footnote · HeaderFooter
{ "type": "equation", "omml": "…", "latex": null, "numbering": "(4)" }
{ "type": "page_break" }
{ "type": "header_footer", "kind": "header|footer", "variant": "default|first|even", "children": [Block…],
  "has_page_number_field": true }

// ReferenceEntry (bibliography item)
{ "type": "reference_entry", "label": "[3]", "runs": [Run…], "reference_id": "ref_3",  // → references table
  "parsed": { "csl_type": "article-journal", "confidence": 0.82 } }
```

### 7.4 Slides (PPTX)

```jsonc
{ "type": "slide", "index": 3, "layout": "Title and Content", "size_pt": [960, 540],
  "title_id": "n_t3", "notes": [Block…], "hidden": false,
  "shapes": [
    { "id": "n_sh5", "kind": "text|picture|table|chart|group|placeholder",
      "placeholder_type": "body", "bbox_pt": [48, 120, 864, 380], "rotation": 0,
      "text": [Block…],                       // paragraphs with fmt
      "autofit": "none|normal|shape",
      "z": 2, "asset_id": null }
  ] }
```

### 7.5 Layout overlay (from rendering, stored separately)

The render job produces a `LayoutMap` per version: for each page or slide, the text spans and boxes with bboxes (from PyMuPDF), mapped back to ADM node IDs by text alignment (fuzzy, with confidence). Visual checks and finding highlights use this map. It's kept separate from the ADM because it depends on the renderer.

### 7.6 Operations (the only way to change an ADM)

```jsonc
{ "op": "set_run_fmt",       "node_id": "…", "run_range": [0, 3], "props": { "font_family": "Times New Roman" } }
{ "op": "set_para_fmt",      "node_id": "…", "props": { "space_after_pt": 6 } }
{ "op": "set_style_fmt",     "style": "Heading1", "props": { "size_pt": 10, "small_caps": true } }
{ "op": "set_page_setup",    "page_setup_id": "ps1", "props": { "margins_pt": { "left": 54 } } }
{ "op": "replace_text",      "node_id": "…", "before": "…", "after": "…" }   // 'before' guards against staleness
{ "op": "set_heading_level", "node_id": "…", "level": 2 }
{ "op": "set_numbering",     "node_id": "…", "label": "3" }
{ "op": "insert_block",      "after_id": "…", "block": { … } }
{ "op": "delete_block",      "node_id": "…" }
{ "op": "move_block",        "node_id": "…", "after_id": "…" }
{ "op": "set_caption",       "target_id": "fig_3", "caption": { … } }
{ "op": "replace_reference", "node_id": "…", "runs": [ … ] }
```

Each format's patcher declares which ops it supports. A proposal whose op the target format's patcher doesn't support is shown as "manual fix required", never silently dropped.

---

## 8. UDSE rule schema

### 8.1 Standard profile

```yaml
standard: ieee-conference
version: 1.0.0
extends: null                       # or another standard_version id
applies_to: [docx, pdf]
meta:
  name: "IEEE Conference Paper"
  sources:
    - id: src1
      title: "<official IEEE author guide — exact title/URL recorded in Phase 4>"
      url: "…"
      retrieved: 2026-…
rules: [ Rule… ]
```

### 8.2 Rule

```yaml
- id: page.margin.left              # unique within profile
  title: "Left margin"
  category: page                    # page|typography|structure|references|figures_tables|layout
  kind: hard                        # hard | soft
  severity: high                    # default severity when violated
  applies_to: [docx, pdf]
  selector:                         # what the rule targets
    node: page_setup                # page_setup|paragraph|heading|run|table|figure|caption|
                                    # section|reference_entry|slide|shape|document
    where:                          # optional filters
      # e.g. { level: 1 } | { role: abstract } | { style_ref: Normal } | { section_role: references }
  check:
    op: in_range                    # see operator library
    property: margins_pt.left
    min: 53.5
    max: 54.5                       # (illustrative numbers only)
    unit: pt
  tolerance: { abs: 0.5 }
  message: "Left margin is {actual} but must be {expected}."
  fix:
    strategy: set_page_setup        # maps to a fixer / ADM op
    auto: true                      # can be proposed automatically
    risk: formatting_only
  provenance:                       # REQUIRED for extracted/builtin rules
    source: src1
    locator: "Section 3, p. 2"
    quote: "<verbatim sentence from the source>"
    verified: true                  # quote found verbatim in source text (§8.5)
  enabled: true
```

### 8.3 Operator library (deterministic)

| `op` | Meaning | Example |
|---|---|---|
| `equals` / `not_equals` | property equality (with unit normalisation and tolerance) | paper = A4 |
| `in_set` | value ∈ allowed set | font_family ∈ {Times New Roman, Times} |
| `in_range` | min ≤ value ≤ max | body size 10–12 pt |
| `matches` | regex over text/label | caption label `^Fig\. \d+\.` |
| `present` / `absent` | the selector must or must not match ≥1 node | an Abstract section exists |
| `count` | number of matches within bounds | keywords 3–6 |
| `max_words` / `min_words` | word count over the selected text | abstract ≤ 250 words |
| `order` | sections appear in the given role order | intro → … → conclusion → references |
| `sequence` | numbering is continuous and well-formed | figures 1,2,3…; headings I, A, 1 |
| `hierarchy` | no level skips | H1 → H3 forbidden |
| `consistent` | all selected nodes share a property value | all H2s use the same size |
| `all_have` | every selected node has a related node | every figure has a caption |
| `referenced_in_text` | every figure/table has an xref before or near it | |
| `citation_style` | in-text citations and entries conform to a CSL style | IEEE numeric `[n]` |
| `reference_order` | bibliography ordering | order of first citation / alphabetical |
| `field_format` | a CSL field matches a format | DOI as `https://doi.org/…` |

Operators are pure functions `(nodes, params) -> list[Violation]`. Adding an operator takes a function and a JSON Schema fragment.

### 8.4 Soft rules

```yaml
- id: style.abstract.self_contained
  kind: soft
  category: structure
  severity: low
  selector: { node: section, where: { role: abstract } }
  check:
    op: llm_assess
    rubric: "Abstract states problem, method, key result, and conclusion."   # must come from the source
    output: { verdict: [meets, partially, does_not_meet], evidence_span: required }
  provenance: { source: src1, quote: "…" }
```

An LLM may **evaluate** a soft rule against a rubric that the standard itself provides. It may never create the rubric. A soft-rule result always shows as "model-assessed" with the quoted evidence span from the document. A soft rule can't be `kind: hard`, and its result can't affect the hard-constraint cap.

### 8.5 Guarding rule extraction against invention

The Custom Standard Builder extracts candidate rules from guideline documents in three ways:
1. **Pattern extraction** (deterministic): regexes and grammars for common phrasings ("margins of 1 inch", "12-point Times New Roman", "double-spaced", "A4").
2. **LLM extraction**: the model receives guideline chunks and must return rules in the exact schema, **each with a verbatim `quote`** and the chunk ID.
3. **Sample inference**: measure formatting statistics from sample documents. These are labelled **"observed in samples"**, never "required", until the user confirms them.

Then, deterministically:
- **Quote verification.** The quote must appear in the source text (after whitespace and Unicode normalisation). If it doesn't, the candidate is marked `evidence_verified=false` and **can't be auto-accepted**.
- **Value grounding.** Every numeric value in the rule must also appear in the quote, with unit conversion (for example, the rule says `54pt` and the quote says `0.75 in`).
- **Schema validation** against the rule JSON Schema.
- **Human review is mandatory.** Nothing enters a published standard without an explicit accept or edit.

---

## 9. Phase-by-phase implementation plan

Each phase ends with a runnable application, green CI, and a completion report that lists what was **actually verified**.

### PHASE 1 — Foundation
- **Objective:** a running skeleton with auth, secure upload and immutable storage, and the first document library page.
- **Files:** `docker-compose.yml`, `.env.example`, `Makefile`, `infra/docker/*`, `backend/pyproject.toml`, `backend/app/{main.py, core/*, db/*, api/deps.py, api/v1/{auth,documents,jobs}.py, services/{auth,documents,jobs}/*, adapters/storage/*, workers/celery_app.py}`, initial Alembic migration (users, refresh_tokens, blobs, documents, document_versions, jobs, audit_events), `frontend/` scaffold (Vite+TS+Tailwind, router, AppShell, auth pages, Dashboard, Library with upload), `docs/adr/0001-0005`.
- **Implementation details:** app factory, settings via pydantic-settings, structured logging with request ID, error envelope, Argon2id, JWT + refresh rotation with reuse detection, rate-limited login, `filesafety.validate_upload` (magic bytes via `python-magic`/manual signatures, OOXML zip guard, macro rejection, size limits), content-addressed blob storage (local + S3), upload creates document + v1 (a parse job stub is **not** created until Phase 2; status stays `ready` with "not yet analysed"), generated OpenAPI client, CI (ruff, mypy, pytest, eslint, tsc, vitest, import-linter).
- **Dependencies:** fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic, argon2-cffi, pyjwt, python-multipart, defusedxml, celery, redis, boto3 (S3 adapter only); react, react-router, @tanstack/react-query, zustand, tailwindcss, openapi-typescript.
- **Testing:** unit (hashing, token rotation and reuse detection, filesafety against crafted zip bombs / wrong extension / `.docm` / path traversal), integration (register → login → upload → list → download the original, byte-identical by sha256; user B can't see user A's document → 404), frontend component tests for auth and upload.
- **Acceptance criteria:** `make dev` brings up the stack; a new user can register, log in, upload DOCX/PDF/PPTX, see the document in the library and download the identical original; invalid or malicious files are rejected with clear messages; all tests pass; no secrets in the repo (CI secret scan).
- **Status: ✅ Complete — verified 2026-11-07.**

  | Check | Result |
  |---|---|
  | Backend tests (pytest: 46 unit + 35 integration against real PostgreSQL 16 + Redis 7, schema built by the real migrations) | 81 passed |
  | Frontend tests (Vitest) | 13 passed |
  | `ruff`, `ruff format`, `mypy --strict`, `import-linter` (2 architecture contracts), `tsc`, `eslint` | all clean |
  | Migration round trip (`upgrade → downgrade → upgrade`, `alembic check`) | clean, no drift |
  | Browser E2E (`e2e/phase1.e2e.mjs`, Chromium, 16 checks) against Vite dev server **and** the Docker stack | all passed |
  | `docker compose up` (db, redis, api, worker, web/nginx): readiness + real Celery round trip | healthy, `pong` |
  | Database refuses `UPDATE`/`DELETE` on originals (trigger) | verified in tests and in Docker |
  | CI workflow (`.github/workflows/ci.yml`, incl. gitleaks secret scan) | written; **not yet run** (no GitHub remote) |

  **Differences from the plan (deliberate):**
  - S3 storage adapter deferred: only the local adapter exists, behind the `BlobStorage` interface. It will be added and tested against MinIO when deployment needs it.
  - No parse job is created on upload; that arrives with the parser in Phase 2. Versions honestly report `analysis: not_available`.
  - Added `GET /documents/stats` for the dashboard and `GET /capabilities` so the UI shows unbuilt modules as locked.
  - Zustand dropped: React context covers the small amount of client state.
  - UI motion uses vendored React Bits components (ADR 0005).
  - TypeScript `noUncheckedIndexedAccess` is off because vendored React Bits code does not compile with it; `strict` stays on.
  - Bugs found during verification and fixed: benign PDFs falsely flagged for `/OpenAction`; the production image lacked `packaging`, which Celery's Redis transport needs; mobile sidebar caused horizontal scroll; the sign-in hero text was pushed off-screen by the WebGL background.

### PHASE 2 — Document intelligence
- **Objective:** parse all three formats into the ADM, render pages, and preview them.
- **Files:** `domain/adm/*`, `adapters/formats/{base, docx/importer, pdf/importer, pptx/importer}.py`, `adapters/render/*`, `workers/tasks/{parse,render}.py`, `api/v1/versions.py`, migration (document_assets, render_pages), `tests/fixtures/build_fixtures.py`, frontend `features/workspace/{StructureTree, PageViewer, AdmTextView}`.
- **Implementation details:** DOCX: style inheritance resolution (docDefaults → style chain → direct formatting), sections, numbering (`numbering.xml`), tables, images, captions (style- and field-based), headers/footers, footnotes. PDF: PyMuPDF `get_text("dict")` blocks/spans → paragraphs; heading inference by font size/weight clusters (`fidelity: inferred`); tagged-PDF structure when present; tables via `page.find_tables()` (inferred). PPTX: slides, shapes, placeholders, text frames, notes. Sandboxed LibreOffice render (timeout, ulimit, temp profile, no network), PNG rasterisation, LayoutMap.
- **Dependencies:** python-docx, python-pptx, PyMuPDF, lxml; LibreOffice and Noto fonts in the worker image.
- **Testing:** golden tests: each fixture → expected ADM snapshot (outline, counts, key formatting); round-trip property tests (parse → serialise → parse is stable); render smoke tests; a corpus of real-world samples for crash resistance (no exception on any file).
- **Acceptance:** an uploaded file shows a structure tree and page previews; ADM is downloadable; fidelity flags are correct for PDF-inferred properties; parse failures produce a clear job error, not a crash.
- **Status:** Not started.

### PHASE 3 — Inspection engine
- **Objective:** structural and formatting inspection with severity-classified findings and a quality report.
- **Files:** `domain/inspection/{registry, checks/*}.py`, `domain/scoring/*`, `services/inspections`, `services/reports`, `api/v1/{inspections,reports}.py`, migration (inspection_runs, findings, compliance_reports), frontend inspection report, finding overlays, quality dashboard v1.
- **Checks (initial set):** heading hierarchy skips, inconsistent heading formatting per level, numbering gaps/duplicates (headings, figures, tables, equations), missing captions, figures/tables never referenced, font inconsistencies in body text (outlier detection against the dominant style), spacing inconsistencies, margin inconsistencies across sections, empty paragraphs/pages, broken tables (ragged rows, zero-width columns), page numbering missing/discontinuous, metadata missing (title/author), empty headers/footers.
- **Testing:** each fixture in `manifest.yaml` must produce exactly its expected findings (precision and recall measured on the fixture set); clean documents must produce no findings above `low`.
- **Acceptance:** 100% of manifest-declared violations detected on fixtures; zero false positives of `high`/`critical` on the clean fixtures; every finding has a location, explanation and recommendation.
- **Status:** Not started.

### PHASE 4 — UDSE
- **Objective:** standard profiles, machine-readable rules, deterministic validation and compliance reports.
- **Files:** `domain/udse/*`, `standards/builtin/*.yaml`, `docs/standards-sources.md`, `services/standards`, `api/v1/{standards,validations}.py`, migration (standards, standard_versions), frontend standards list/detail/rule editor, compliance tab.
- **Implementation details:** rule JSON Schema (published at `/udse/rule-schema`), selector engine, operator library, unit normalisation and tolerance, inheritance (`extends` + override by rule ID), hard/soft separation, the scoring cap, rule-level `not_evaluated`. Built-in IEEE/APA/MLA profiles are written from official sources, and every rule has a citation (reviewed before merge). Basic pattern-based rule extraction from guidelines (the full builder comes in Phase 9).
- **Testing:** an operator unit test for every operator (pass, fail, boundary, tolerance, unit conversion); one fixture per built-in standard with known violations; property test: validation is deterministic (same input gives the same output and the same hash).
- **Acceptance:** validating a fixture against IEEE/APA/MLA reproduces the expected rule results exactly; editing a custom standard and re-validating reflects the change; no rule without provenance can be published in a built-in profile.
- **Status:** Not started.

### PHASE 5 — Editing & correction
- **Objective:** tracked AI and grammar editing, and approval-gated auto-correction with revalidation.
- **Files:** `domain/{changes,correction}/*`, `adapters/formats/{docx,pptx}/patcher.py`, `adapters/llm/*`, `adapters/languagetool.py`, `services/{editing,corrections,versions}`, `api/v1/{changesets,editing}.py`, migration (changesets, change_proposals, llm_calls), frontend ChangeSet panel, diff view, TipTap paragraph editor, version history page.
- **Implementation details:** fixers for formatting, heading, numbering, spacing, font, margin, caption and reference format; DOCX/PPTX patchers that edit the OOXML of the original (preferring style-level changes); stale-base detection (`409`); LanguageTool integration; LLM edit operations with structured output; meaning-preservation warning; apply → new version → re-render → revalidate → diff of the compliance report (before/after).
- **Testing:** fixture → validate → accept all auto-fixes → apply → revalidate: the targeted violations are gone and **no new violations appear**; the patched DOCX opens in LibreOffice and python-docx; the original blob is unchanged (hash check); rejected proposals aren't applied; LLM adapter tested against a recorded-response stub (tests only, never production), plus an opt-in live test.
- **Acceptance:** the full approve → apply → revalidate loop works end to end for DOCX and PPTX; PDF shows report-only with the "Rebuild as DOCX" option; nothing changes without explicit acceptance.
- **Status:** Not started.

### PHASE 6 — Document generation
- **Objective:** generate the ten document types from a brief, with an editable outline, section-by-section generation and DOCX/PDF export.
- **Files:** `services/generation/*` (per-type templates and prompts), `adapters/formats/docx/exporter.py`, `adapters/formats/pdf/exporter.py` (ReportLab, or DOCX → LibreOffice → PDF for fidelity; decision recorded in an ADR), `services/exports`, frontend `/create` flow.
- **Implementation details:** word-count control per section; tone and style parameters; citations only from the user's `references` (otherwise a visible placeholder); generated output is a new document, validated against the selected standard right away; generated nodes marked as such in the UI.
- **Testing:** schema validation of the generated ADM; exported files open and re-import to an equivalent ADM; word targets within ±10%; a test that **no citation is emitted without a backing reference record**.
- **Acceptance:** each document type can be produced end to end and exported; the generated document passes structural inspection with no critical findings.
- **Status:** Not started.

### PHASE 7 — Presentation engine
- **Objective:** PPTX generation with themes, layouts, speaker notes, slide numbers and validation.
- **Files:** `services/presentations/*`, `adapters/formats/pptx/exporter.py`, `backend/themes/*.pptx` (in-house master templates), `domain/visual/slides.py`, frontend presentation flow.
- **Implementation details:** outline → slide plan (layout per slide) → content fitting (character budgets per placeholder estimated from font metrics, then verified by render) → PPTX → render → slide checks (overflow, clipping, alignment, typography consistency, density/balance) → automatic re-fit proposals.
- **Testing:** generated decks render with zero overflow findings on the standard test briefs; fixtures with deliberate overflow are detected.
- **Acceptance:** decks open in LibreOffice/PowerPoint, theme is consistent, notes and numbering present, validation report shown.
- **Status:** Not started.

### PHASE 8 — Visual quality engine
- **Objective:** render-based defect detection for all formats, with page- and slide-specific reports.
- **Files:** `domain/visual/*`, `services/visual`, frontend overlays and visual score.
- **Implementation details:** deterministic geometry first (bbox beyond page/margins, text in ADM missing from rendered text → clipping, blank pages by pixel variance, table width vs. text block, image placement vs. columns, widow/orphan heuristics, alignment deviation clustering). An optional vision-model pass for composition and hierarchy is labelled "model-assessed" and kept out of hard scores.
- **Testing:** fixtures with known visual defects (overflowing table, blank page, off-margin image, clipped text box); measure precision and recall.
- **Acceptance:** all fixture visual defects detected with correct page/slide and bbox; no high-severity false positives on clean fixtures.
- **Status:** Not started.

### PHASE 9 — Research & advanced AI
- **Objective:** source discovery, reference verification, RAG over guidelines, the full Custom Standard Builder.
- **Files:** `adapters/scholarly/*`, `domain/references/*`, `services/research`, `adapters/embeddings`, migration (references, guideline_chunks, rule_extraction_candidates), frontend references manager and standard builder wizard.
- **Implementation details:** DOI resolution and metadata matching (title similarity, authors, year) → `verified`/`mismatch`/`not_found`; URL checks with SSRF protection (block private IPs, limit redirects); CSL formatting (citeproc-py); search through OpenAlex/Crossref (results stay `suggested`); guideline chunking + pgvector; LLM extraction with quote verification (§8.5); sample-document inference.
- **Testing:** recorded HTTP fixtures for Crossref/OpenAlex; a fabricated DOI → `not_found`; a real DOI with a wrong year → `mismatch`; an extraction test where the model returns a quote not in the source → rejected from auto-accept.
- **Acceptance:** no reference is shown as verified without a stored matching record; the builder produces a usable standard from a sample guideline after human review.
- **Status:** Not started.

---

## 10. Technical risks and mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | **DOCX round-trip loses content or formatting** when regenerated from an intermediate model. | High — damaged user documents. | Patch-based export onto the original OOXML (D6); unknown XML preserved; post-apply re-import + diff check that only the intended nodes changed; originals immutable. |
| R2 | **PDF has no reliable structure** (headings, tables, reading order are inferred). | False findings. | Fidelity flags; inferred values lower confidence and severity; tagged-PDF use when present; PDF corrections report-only (D5). |
| R3 | **LibreOffice renders differently from Word/PowerPoint** (fonts, line breaking). | Visual findings that don't occur in Word. | Ship the common metric-compatible fonts (Liberation, Carlito, Caladea, Noto); report a "font substituted" info finding; visual findings carry "rendered with LibreOffice" context; tolerances on geometric checks. |
| R4 | **LLM invents formatting rules, references or facts.** | Loss of trust; academic harm. | Hard rules are deterministic only; extraction requires a verbatim quote + value grounding + human review (§8.5); citations only from reference records; verification statuses explicit; structured output validated, retries, then hard failure. |
| R5 | **Malicious uploads** (zip bombs, XXE, macros, PDF JavaScript, embedded OLE, path traversal). | Security compromise. | `filesafety` gate; defusedxml; macros stripped/rejected and never executed; rendering in a sandboxed, non-root, network-less container with CPU/memory/time limits; ClamAV hook optional. |
| R6 | **Rendering/parsing large documents is slow** or LibreOffice hangs. | Poor UX, stuck workers. | Separate queues with concurrency limits; hard timeouts and process-group kill; page caps; progress via SSE; render once per version and cache. |
| R7 | **Privacy of sending documents to external LLMs.** | Data exposure. | Off by default; per-user consent; provider abstraction allows a local model (Ollama); no prompt content in logs; LanguageTool self-hosted. |
| R8 | **Heading/section detection when authors don't use styles** (bold "Heading" paragraphs). | Missed structure findings. | Heuristic classifier (font size/weight/numbering patterns) with `inferred` fidelity; an explicit finding "headings not using heading styles" (useful in itself). |
| R9 | **Standards are copyrighted or ambiguous, or change over time.** | Wrong built-in rules. | Rules cite sources and the version date; profiles versioned; "verify against your venue" notice; easy institutional overrides via `extends`. |
| R10 | **Scope size** (9 modules). | Never-finished platform. | Strict phase gates; every phase shippable; fixtures as acceptance tests; features hidden via `/capabilities` until real. |
| R11 | **Concurrent edits / stale ChangeSets.** | Lost or misapplied changes. | `base_version_id` + `409` on stale apply; `replace_text` ops carry a `before` guard; optimistic locking on document `current_version_id`. |
| R12 | **External API limits** (Crossref/OpenAlex rate limits, outages). | Verification incomplete. | Polite-pool headers with a configurable contact, caching, backoff; failures yield `error`/`unverified`, never `verified`. |
| R13 | **Mapping rendered layout back to ADM nodes is imprecise.** | Highlights in the wrong place. | Fuzzy text alignment with confidence; fall back to page-level location when confidence is low. |
| R14 | **Indic/complex scripts** (shaping, LanguageTool coverage). | Wrong measurements, missing grammar. | Noto fonts with HarfBuzz-based rendering in LibreOffice; per-run `lang`; explicit "language not supported" result. |
| R15 | **Cost and latency of LLM calls.** | Expensive, slow. | LLM used only for semantic tasks; section-scoped prompts; caching by prompt hash; token accounting in `llm_calls`; per-user quotas. |

---

**Next step:** review the decisions in §0 and the plan in §9. Once you approve, or tell me what to change, I'll start **Phase 1 — Foundation**.
