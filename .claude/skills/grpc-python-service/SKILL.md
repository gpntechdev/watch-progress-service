---
name: grpc-python-service
description: Use when writing or changing server code in server/ (servicer, interceptors, startup).
---

# Server code conventions

Source of truth: `docs/DESIGN.md` (sections 4, 11).

- Use `grpc.aio` (async) throughout. No blocking calls in handlers.
- **Deadlines:** unary calls get a 5 s default when the client sets none; check `context.time_remaining()` and pass it to Redis/PostgreSQL calls. `StreamProgress` is not covered by that default: 55 minute deadline, 10 minute idle timeout, and the client reopens with the same `session_id`.
- **Status codes**, never leak raw exceptions; use `await context.abort(code, message)`: bad field or bad `page_token` → `INVALID_ARGUMENT`; missing/unknown token → `UNAUTHENTICATED`; over 40 requests/min per user → `RESOURCE_EXHAUSTED`; `GetProgress` with nothing stored, or `RemoveFromContinueWatching` for a video not in the row → `NOT_FOUND`; Redis and PostgreSQL both down, or `wp:dirty` at its cap → `UNAVAILABLE`; deadline → `DEADLINE_EXCEEDED`.
- **Validation:** position ≥ 0 and ≤ the video's duration, non-empty and known `video_id` (video list held in memory, loaded from `videos` at startup). `client_time` missing or more than 15 min in the future is clamped to server time. `page_size` default 25, max 100 (larger is reduced); negative → `INVALID_ARGUMENT`.
- **Auth interceptor:** hash the presented token (SHA-256), look it up in `user_tokens` held in memory (loaded at startup; no database call per request), store the user ID for the handler. For streams, check once at open. Never take the user from a request field.
- **Rate limit:** 40 requests per minute per user, counted in process. In a stream an over-limit event is dropped and the stream stays open.
- **Streams:** an invalid event is skipped and the stream continues; `events_accepted` counts valid events processed (including an older one that lost the comparison). An abnormal end (cancel, reset) counts as a stream close and flushes the key.
- Logs are structured (key=value or JSON) and include method, user id, status and duration. Never log tokens.
- Register the health service and reflection on the server.
- New RPC path: `.proto` (see `proto-api`) → `make gen` → servicer method → test → client.
- Servicers stay thin; domain logic lives in its own module so it can be tested without gRPC.

Do not write the Lua script, flusher or conflict rules without asking (see CLAUDE.md and `progress-domain-rules`).
