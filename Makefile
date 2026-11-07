# AKSHARA developer commands. Run `make help`.
.PHONY: help install dev-api dev-web migrate test test-backend test-frontend lint e2e up down smoke gen-api

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-15s %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	cd backend && uv sync
	cd frontend && npm ci

migrate: ## Apply database migrations (uses backend/.env)
	cd backend && uv run alembic upgrade head

dev-api: ## Run the API with auto-reload on :8000
	cd backend && uv run uvicorn app.main:create_app --factory --reload --port 8000

dev-web: ## Run the web UI on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

gen-api: ## Regenerate frontend API types from the running API
	cd frontend && npm run gen:api

test: test-backend test-frontend ## Run all automated tests

test-backend: ## Backend unit + integration tests (needs PostgreSQL + Redis)
	cd backend && uv run pytest -q

test-frontend: ## Frontend unit tests
	cd frontend && npx vitest run

lint: ## Lint, format check, type-check and architecture contracts
	cd backend && uv run ruff check app tests migrations && uv run ruff format --check app tests migrations \
		&& uv run mypy app && uv run lint-imports
	cd frontend && npx tsc -b --noEmit && npx eslint .

e2e: ## Browser end-to-end check (needs the stack running; see e2e/README.md)
	node e2e/phase1.e2e.mjs $(SAMPLES)

up: ## Build and start the full Docker stack on :8080
	docker compose up -d --build

down: ## Stop the Docker stack (data volumes are kept)
	docker compose down

smoke: ## Verify the running stack: readiness + a real Celery round trip
	curl -fsS localhost:8080/api/v1/ready && echo
	docker compose exec -T api python -c "from app.workers.celery_app import celery_app as c; print('worker:', c.send_task('system.ping').get(timeout=30))"
