.PHONY: up down test lint gen dev migrate seed-demo run-server

up:    ## start PostgreSQL + Redis and wait until healthy
	docker compose up -d --wait

down:  ## stop the stack (data volume is kept)
	docker compose down

migrate:  ## apply database migrations (run `make up` first)
	cd server && uv run alembic upgrade head

seed-demo:  ## insert demo videos, users and watch history (idempotent)
	cd server && uv run seed-demo

run-server:  ## start the gRPC server on :50051 (needs make up, migrate, seed-demo)
	cd server && uv run python -m watch_progress_service.server

test:  ## server unit/integration tests
	cd server && uv run pytest

lint:  ## proto lint, Python lint, TypeScript lint
	buf lint
	cd server && uv run ruff check .
	pnpm -C web lint

gen:   ## regenerate Python + TypeScript code from proto/
	buf generate

dev:   ## web dev server (a server target is added in Phase 1)
	pnpm -C web dev
