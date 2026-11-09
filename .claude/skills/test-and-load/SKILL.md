---
name: test-and-load
description: Use when writing tests or measuring performance (pytest, Playwright, k6).
---

# Testing and load

- **Server:** pytest with testcontainers (real PostgreSQL and Redis, not mocks) for anything on the write path. Run with `make test`.
- **Web:** Playwright two-device scenario: watch on "device A", resume at the same spot on "device B".
- **Load:** k6 with its gRPC streaming support, script at `load/stream.js`, N concurrent client streams against the **local** docker-compose stack only. Never against the Cloud Run demo.
- **Record in the README and the design doc:** heartbeats/s sustained, p99 latency, and the write-reduction ratio = heartbeats received ÷ PostgreSQL row writes. Note machine, N streams, flush interval and batch size so numbers are reproducible.
- Every change ships with tests. Cover the edge cases: out-of-order `client_time`, exactly 90%, duplicate batch replay, Redis cold start.
