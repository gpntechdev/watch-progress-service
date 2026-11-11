.PHONY: up down test lint gen dev

up:    ## start PostgreSQL + Redis and wait until healthy
	docker compose up -d --wait

down:  ## stop the stack (data volume is kept)
	docker compose down

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
