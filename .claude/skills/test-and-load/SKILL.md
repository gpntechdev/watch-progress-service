---
name: test-and-load
description: Use when writing tests or measuring performance (pytest, Playwright, k6).
---

# Testing and load

Source of truth: `docs/DESIGN.md` sections 2 and 8.

- **Server:** pytest with testcontainers (real PostgreSQL and Redis, not mocks) for anything on the write path. Run with `make test`.
- **Web:** Playwright two-device scenario: watch on "device A", resume at the same spot on "device B".
- **Load:** k6 with its gRPC streaming support, script at `load/stream.js`, N concurrent client streams against the **local** docker-compose stack only. Never against the Cloud Run demo.
- **Users and tokens:** the load test uses generated users seeded by `seed-loadtest` (local database only; it must refuse any other URL). Tokens are derived from the user index so k6 can compute them. The per-user rate limit (40 requests/min) makes a few users unusable at load.
- **Targets (demo scale):** 2,000–4,000 heartbeats/s; p99 under 20 ms (unary: handler time; streams: per-event processing time; excludes network and Envoy); write reduction about 6× for continuous playback (about 5.7× with 1% extra reports). Record heartbeats/s sustained, p99, and the ratio = heartbeats received ÷ PostgreSQL row writes in the README and design doc, with machine, N streams, flush interval and batch size.
- Every change ships with tests. Edge cases: out-of-order `client_time`; equal `client_time` (tie by `session_id`); `client_time` more than 15 min in the future; exactly 90%; rewatch unfinishes and clears `removed`; duplicate batch replay; key rewritten during a flush (compare-and-remove); Redis cold start; Redis down; PostgreSQL down and the `wp:dirty` cap; stream cancelled mid-session; invalid event in a stream; over-limit event in a stream.
