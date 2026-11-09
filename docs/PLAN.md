# Watch-Progress Service — Project Plan

Nov 9, 2026 · @Andrii Hapon

## Overview

You'll build a "Continue watching" backend in Python with gRPC, plus a React/TypeScript player that uses it. It's about 40–50 hours part-time (3–4 weeks) and costs close to $0 a month to keep online for a demo.

**What it does**

- While a video plays, the player streams its position to the server every 5 seconds over one long-lived gRPC client stream.
- The server keeps the latest position per user and video in Redis, and writes to PostgreSQL in batches every few seconds instead of on every heartbeat.
- When a user opens the app, they get a "Continue watching" row: unfinished videos sorted by last watched, with a progress bar on each.
- Videos watched past 90% count as finished and leave the row; the user can also remove a video from it.
- The same user on two devices resumes from the furthest-recent position: last write wins, compared by event time and not arrival time.

**Out of scope:** real video hosting (use 5–10 public-domain sample videos), recommendations, sign-up flows (use a simple demo login with a few fixed users).

**Target CV bullet:** *Built a watch-progress service (Python, gRPC client streaming, Redis, PostgreSQL) with a React/TypeScript player; sustained \[X\]k heartbeats/s at p99 \[X\] ms in k6 load tests, cutting database writes \[X\]× through Redis write-behind batching. Deployed on Cloud Run.*

## Architecture

&#91;embedded content: watch-progress architecture · 2 clients, 1 service, 2 stores\]

Both clients write to the same Python gRPC service: the browser through Envoy, the TV simulator directly with client streaming. The "Continue watching" row is read from Redis, falling back to PostgreSQL when the cache is cold.

## Tech stack and API

One design fact shapes the API: **browsers can't do gRPC client streaming.** gRPC-Web and Connect in the browser support only unary and server-streaming calls. So the service has two write paths: the web player sends a small unary report every 5 seconds, and a Python "TV device" simulator (plus the k6 load test) uses true client streaming. Explaining that trade-off is a good interview answer in itself.

| Layer | Choice | Why |
| --- | --- | --- |
| API contract | Protocol Buffers, linted with `buf` (lint + breaking-change check) | Google's own style; `buf breaking` shows you understand schema evolution |
| Server | Python 3.12, `grpcio` with `grpc.aio` (async), `uv` for packages | Standard Google gRPC library; async handles thousands of open streams |
| Browser bridge | Envoy gRPC-Web filter as a Cloud Run sidecar | Translates browser gRPC-Web into native gRPC. Fallback if Envoy eats too much time: `connectrpc` for Python (beta, v0.11) |
| Hot storage | Redis: latest position per user and video, plus a "dirty" set for batching | Absorbs heartbeats; one PostgreSQL write per video every few seconds instead of per heartbeat |
| Durable storage | PostgreSQL via SQLAlchemy 2 (async) + Alembic migrations | Source of truth; `UPSERT … WHERE excluded.event_time > event_time` gives last-write-wins |
| Frontend | React + TypeScript + Vite, `@connectrpc/connect-web` with the gRPC-Web transport, TanStack Query | Your strongest area; generated, typed client |
| Testing | pytest + testcontainers, Playwright, k6 (has gRPC streaming support) | Real numbers for the CV bullet |
| Delivery | Docker, GitHub Actions, Cloud Run | Google Cloud fits a Google application |

**API sketch (`proto/watchprogress/v1/watch_progress.proto`)**

```protobuf
syntax = "proto3";
package watchprogress.v1;

import "google/protobuf/timestamp.proto";

service WatchProgressService {
  // Web player: unary, one report every ~5 s and on pause, seek or tab hide.
  rpc ReportProgress(ReportProgressRequest) returns (ReportProgressResponse);
  // TV / device path: one long-lived client stream per playback session.
  rpc StreamProgress(stream ProgressEvent) returns (StreamProgressSummary);
  rpc GetProgress(GetProgressRequest) returns (GetProgressResponse);
  rpc ListContinueWatching(ListContinueWatchingRequest) returns (ListContinueWatchingResponse);
  rpc RemoveFromContinueWatching(RemoveFromContinueWatchingRequest) returns (RemoveFromContinueWatchingResponse);
}

message ProgressEvent {
  string video_id = 1;
  int32 position_seconds = 2;
  int32 duration_seconds = 3;
  google.protobuf.Timestamp client_time = 4; // decides last-write-wins
  string session_id = 5;                     // one playback session
}

message ReportProgressRequest { ProgressEvent event = 1; }
message ReportProgressResponse {}
message StreamProgressSummary { int32 events_accepted = 1; }

message ListContinueWatchingRequest {
  int32 page_size = 1;
  string page_token = 2; // opaque cursor, AIP-158 style
}
message ListContinueWatchingResponse {
  repeated VideoProgress items = 1;
  string next_page_token = 2;
}
// VideoProgress, Get* and Remove* messages follow the same pattern.
```

The user ID comes from the auth metadata (a demo token), never from the request body. That's a security point interviewers like.

**Storage model**

- PostgreSQL `watch_progress`: `user_id`, `video_id`, `position_s`, `duration_s`, `event_time`, `finished`, `updated_at`; primary key `(user_id, video_id)`, index on `(user_id, event_time DESC)`.
- Redis: hash `wp:{user}:{video}` for the latest position; sorted set `cw:{user}` scored by event time for the row; set `wp:dirty` of keys waiting to be flushed. A Lua script makes "compare event time, then write" atomic.

## Implementation plan

Eight phases, about 47 hours in total. Each phase ends with something you can run, so you can stop after any phase and still have a working demo.

| # | Phase | What you build | Done when | Hours |
| --- | --- | --- | --- | --- |
| 0 | Setup and design doc | Repo layout (`proto/`, `server/`, `web/`, `deploy/`), `uv`, `buf`, docker-compose with PostgreSQL and Redis, CLAUDE.md and skills, one-page design doc | `docker compose up` works; design doc committed | 4 |
| 1 | API and server skeleton | `.proto` file, `buf lint`, `grpc.aio` server with health check and reflection, auth interceptor (demo token → user ID), `ListContinueWatching` read from PostgreSQL | `grpcurl` returns a list from seeded data | 5 |
| 2 | Write path | `ReportProgress` and `StreamProgress`; Redis Lua script for last-write-wins; write-behind flusher batching upserts to PostgreSQL; ≥90% marks a video finished; deadlines and proper status codes | Integration tests (testcontainers) pass; restarting the server loses at most one flush interval | 8 |
| 3 | Browser bridge | Envoy gRPC-Web config, CORS, generated TypeScript client (`buf generate` with protobuf-es) | A browser call to `ReportProgress` lands in Redis | 5 |
| 4 | React player | HTML5 player with 5–10 public-domain videos; reports every 5 s and on pause, seek and tab hide; "Continue watching" row with progress bars and remove; keyboard and screen-reader support | Playwright test: watch on "device A", resume at the same spot on "device B" | 6 |
| 5 | Device simulator and load test | Python CLI "TV" using client streaming; k6 script opening N streams; measure p99 latency and the heartbeats-to-database-writes ratio; tune batch size | Numbers recorded in the README and the design doc | 6 |
| 6 | Deploy | Dockerfiles, GitHub Actions (lint, test, `buf breaking`, deploy), Cloud Run with HTTP/2 end-to-end and the Envoy sidecar, managed PostgreSQL and Redis, budget alert | Public demo URL works on your phone | 5 |
| 7 | Learning pass | Rewrite the Lua script and the flusher by hand; write 15 likely interview questions with your answers (scale to 10M viewers, Redis failure, clock skew, hot keys) | You can explain every trade-off without notes | 8 |

**Run load tests locally only** (docker-compose or a temporary VM). Free managed tiers would be used up in minutes, and the numbers would measure their limits, not your code.

**Suggested schedule at about 12 hours a week:** week 1, phases 0–2; week 2, phases 3–4; week 3, phases 5–6; week 4, phase 7 and polishing the README.

## Infrastructure and monthly cost

A demo setup costs about **$0 a month**, because every part fits a permanent free tier at portfolio traffic. Build and test everything locally with docker-compose, and use the cloud only for the public demo.

| Part | Service | Free allowance (as of Nov 2026) | Expected cost |
| --- | --- | --- | --- |
| gRPC server + Envoy sidecar | Google Cloud Run, scale to zero, max 2 instances | Instance-based billing: 240,000 vCPU-seconds and 450,000 GiB-seconds a month; request-based: 180,000 vCPU-seconds, 360,000 GiB-seconds and 2M requests ([pricing](https://cloud.google.com/run/pricing)) | $0. About 20 demo hours a month at 1 vCPU is \~72,000 vCPU-seconds |
| PostgreSQL | Neon Free | $0, 1 GB storage and 100 compute-hours per project, no card needed ([limits](https://neon.com/faqs/free-plan-limits-and-quotas)) | $0 |
| Redis | Upstash Redis Free | 256 MB and 500,000 commands a month ([pricing](https://upstash.com/pricing/redis)) | $0. One viewer is \~2,200 commands an hour, so \~230 viewer-hours a month fit |
| Frontend | Static hosting (Firebase Hosting or Cloudflare Pages free plan) | Check the limits when you sign up | $0 |
| Container images | Google Artifact Registry | Small images, one or two kept | A few cents |
| CI/CD | GitHub Actions | Free for public repositories | $0 |
| Load testing | Your laptop or a VM you delete the same day | — | $0–2 once |

**Above the free tiers:** Cloud Run is $0.000018 per vCPU-second with instance-based billing in Tier 1 regions. Upstash pay-as-you-go is $0.20 per 100,000 commands. Neon Launch is $0.106 per compute-hour. Even a busy demo month stays under about $5.

**Two settings that matter**

- **Use instance-based billing on Cloud Run.** With request-based billing, CPU is throttled between requests, so the background flusher stalls. Instance-based billing keeps it running while an instance is up, and with scale-to-zero you still pay nothing when nobody is watching. Turn on HTTP/2 end-to-end, which gRPC requires.
- **Set a Google Cloud budget alert at $5** before the first deploy, and cap max instances at 2. New Google Cloud accounts also get $300 in free credits for 90 days.

**All-Google alternative:** Cloud SQL and Memorystore look more "Google" on the CV but bill per hour even when idle. Use them only if you will tear them down after recording a demo video.

## Claude Code setup and skills

Give Claude Code one CLAUDE.md for the whole project and six small project skills. The skills keep every session consistent, and one of them makes Claude teach you instead of only writing code. Each skill is a folder `.claude/skills/<name>/` with a `SKILL.md` (a `name`, a one-line `description` saying when to use it, then the instructions), committed to the repo.

**CLAUDE.md (always loaded)**

- The goal in two lines: a portfolio project for a Google full-stack interview, so the code must be clear enough to explain line by line.
- Commands: `docker compose up`, `uv run pytest`, `buf lint && buf generate`, `pnpm -C web dev`, `k6 run load/stream.js`.
- Architecture in five lines, plus a link to the design doc.
- Rules: never edit generated code; every RPC change starts in the `.proto`; tests come with every change; **ask before writing the Lua script, the flusher or the conflict rules**, because you write those yourself.

**Skills to create**

| Skill | Use it when | What it tells Claude |
| --- | --- | --- |
| `proto-api` | Adding or changing an RPC or message | Google API style (AIP naming, `page_token` pagination, field numbers never reused), run `buf lint` and `buf breaking`, regenerate Python and TypeScript, then update both sides |
| `grpc-python-service` | Writing server code | `grpc.aio` patterns, deadlines on every call, mapping errors to gRPC status codes, interceptors for auth and logging, structured logs, how a new RPC goes proto → servicer → test |
| `progress-domain-rules` | Touching the write path or storage | Last-write-wins by `client_time`, the 90% finished rule, Redis key layout, flush batching and idempotent upserts, what may be lost on a crash |
| `web-player-client` | Working in `web/` | Generated client with the gRPC-Web transport, TanStack Query for the row, report timing (5 s, pause, seek, tab hide), accessibility checklist for the player and the row |
| `test-and-load` | Writing tests or measuring | pytest with testcontainers, Playwright two-device scenario, k6 gRPC streaming script, how to record p99 and the write-reduction ratio in the README |
| `deploy-cloud-run` | Building or deploying | Docker build, push to Artifact Registry, Cloud Run flags (instance-based billing, HTTP/2 end-to-end, max 2 instances, Envoy sidecar), secrets via Secret Manager; never load-test the cloud demo |

**One extra skill for learning: `explain-and-quiz`.** At the end of each phase it explains what was built and why, then asks you 5 interview-style questions about it, and logs your weak spots to `notes/interview-gaps.md`. This turns Claude Code into interview preparation, not just a code generator.

**How to work in sessions**

1. Start each phase in plan mode: ask Claude Code for a plan against the phase's "done when" line, and edit the plan before any code is written.
2. Let it write the setup work (Docker, CI, config, boilerplate, tests); write the core logic yourself with Claude reviewing.
3. End every phase with `explain-and-quiz` and a commit.

The built-in `skill-creator` skill can draft these SKILL.md files from this table; review each one before you commit it.

## Sources

- [Cloud Run pricing](https://cloud.google.com/run/pricing) — free tier and per-second rates
- [Neon Free plan limits](https://neon.com/faqs/free-plan-limits-and-quotas) and [Neon free tier comparison](https://neon.com/faqs/managed-postgres-databases-free-tier) — Launch plan rates
- [Upstash Redis pricing](https://upstash.com/pricing/redis) — free tier and pay-as-you-go
- [connectrpc on the Python package index (CERN mirror)](https://simple-repository.app.cern.ch/project/connectrpc) — version 0.11.1, beta status

Prices change; check each page again before you deploy.
