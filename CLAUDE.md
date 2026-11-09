# Watch-Progress Service

Portfolio project for a Google full-stack interview. The owner must be able to explain every line, so keep code clear, small and conventional.
A "Continue watching" backend (Python, gRPC, Redis, PostgreSQL) plus a React/TypeScript player. Full plan: [docs/PLAN.md](docs/PLAN.md).

## Commands
- `make up` / `make down` — PostgreSQL + Redis (`docker compose up -d --wait`)
- `make test` — `cd server && uv run pytest`
- `make lint` — `buf lint`, `ruff check`, `pnpm -C web lint`
- `make gen` — `buf generate` (Python + TypeScript from `proto/`)
- `make dev` — `pnpm -C web dev`
- Later phases: `buf breaking --against '.git#branch=main'`, `k6 run load/stream.js`

## Architecture
- Web player → Envoy (gRPC-Web) → Python `grpc.aio` server. Browsers can't do client streaming, so the web uses unary `ReportProgress` every ~5 s.
- TV/device simulator and k6 → server directly with client-streaming `StreamProgress`.
- Redis holds the latest position per user and video (`wp:{user}:{video}`), a `cw:{user}` sorted set for the row, and a `wp:dirty` set.
- A write-behind flusher batches upserts to PostgreSQL (`watch_progress`, last-write-wins by event time).
- Reads of "Continue watching" come from Redis, falling back to PostgreSQL when cold. User ID comes from auth metadata, never the request body.

## Rules
- Never edit generated code (`server/src/watchprogress/gen/`, `web/src/gen/`); change the `.proto` and run `make gen`.
- Every RPC change starts in `proto/watchprogress/v1/watch_progress.proto`.
- Tests come with every change.
- **Ask before writing the Redis Lua script, the write-behind flusher or the conflict (last-write-wins) rules.** The owner writes these by hand; Claude may review, explain and write tests for them.
- Setup work (Docker, CI, config, boilerplate, tests) Claude writes; core logic the owner writes.
- Work phase by phase from docs/PLAN.md, starting in plan mode. End each phase with the `explain-and-quiz` skill and a commit.
- Never load-test the cloud demo; load tests run locally only.

## Skills (`.claude/skills/`)
`proto-api`, `grpc-python-service`, `progress-domain-rules`, `web-player-client`, `test-and-load`, `deploy-cloud-run`, `explain-and-quiz`.
