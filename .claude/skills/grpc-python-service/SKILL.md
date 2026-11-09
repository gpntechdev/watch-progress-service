---
name: grpc-python-service
description: Use when writing or changing server code in server/ (servicer, interceptors, startup).
---

# Server code conventions

- Use `grpc.aio` (async) throughout. No blocking calls in handlers.
- Every call has a deadline: check `context.time_remaining()` and pass deadlines to Redis/PostgreSQL calls.
- Map errors to gRPC status codes, never leak raw exceptions: bad input → `INVALID_ARGUMENT`, missing/invalid token → `UNAUTHENTICATED`, not found → `NOT_FOUND`, dependency down → `UNAVAILABLE`, deadline → `DEADLINE_EXCEEDED`. Use `await context.abort(code, message)`.
- Interceptors handle cross-cutting work: auth (demo token in metadata → user ID, stored for the handler) and logging.
- Logs are structured (key=value or JSON) and include method, user id, status and duration. Never log tokens.
- Register the health service and reflection on the server.
- New RPC path: `.proto` (see `proto-api`) → `make gen` → servicer method → test → client.
- Servicers stay thin; domain logic lives in its own module so it can be tested without gRPC.

Do not write the Lua script, flusher or conflict rules without asking (see CLAUDE.md and `progress-domain-rules`).
