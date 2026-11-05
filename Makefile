.PHONY: help install dev-api dev-web test lint typecheck build seed up down migrate clean

PY ?= backend/.venv/bin/python

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install backend (venv) and frontend deps
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm ci

dev-api: ## Run the API with reload (SQLite, mock LLM)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-web: ## Run the Next.js dev server
	cd frontend && npm run dev

test: ## Backend tests
	cd backend && .venv/bin/python -m pytest -q

lint: ## Ruff + ESLint
	cd backend && .venv/bin/ruff check .
	cd frontend && npm run lint

typecheck: ## TypeScript
	cd frontend && npx tsc --noEmit

build: ## Production frontend build
	cd frontend && npm run build

seed: ## Seed demo data (demo@revops.dev / demo-password-123)
	cd backend && .venv/bin/python -m scripts.seed

migrate: ## Apply Alembic migrations
	cd backend && .venv/bin/alembic upgrade head

up: ## docker compose up (needs JWT_SECRET in .env)
	docker compose up --build

down:
	docker compose down

clean:
	rm -rf backend/.pytest_cache backend/.ruff_cache frontend/.next backend/*.db
