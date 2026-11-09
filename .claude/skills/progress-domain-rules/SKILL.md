---
name: progress-domain-rules
description: Use when touching the write path, Redis keys or PostgreSQL storage for watch progress.
---

# Domain rules (the owner writes the Lua script, flusher and conflict rules — ask first)

- **Last write wins by `client_time`** (event time), never arrival time. A write with an older `client_time` is ignored.
- **Finished at ≥ 90%** of `duration_seconds`: mark `finished`, remove from the "Continue watching" row. The user can also remove a video manually.
- **Redis keys:** hash `wp:{user}:{video}` (latest position), sorted set `cw:{user}` scored by event time (the row), set `wp:dirty` (keys awaiting flush).
- **Atomicity:** one Lua script compares event time and writes, so the check-then-write cannot race.
- **Flusher:** write-behind; every few seconds read `wp:dirty`, batch the rows, upsert to PostgreSQL, then clear the dirty marker only after commit.
- **Idempotent upsert:** `INSERT … ON CONFLICT (user_id, video_id) DO UPDATE … WHERE excluded.event_time > watch_progress.event_time`. Replaying a batch is safe.
- **PostgreSQL** `watch_progress`: `user_id, video_id, position_s, duration_s, event_time, finished, updated_at`; PK `(user_id, video_id)`; index `(user_id, event_time DESC)`.
- **Crash tolerance:** on server restart at most one flush interval of progress may be lost. Say so in tests and docs.
- Reads: Redis first, PostgreSQL fallback when the cache is cold.
