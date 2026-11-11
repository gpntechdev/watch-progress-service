---
name: progress-domain-rules
description: Use when touching the write path, Redis keys or PostgreSQL storage for watch progress.
---

# Domain rules (the owner writes the Lua script, flusher and conflict rules — ask first)

Source of truth: `docs/DESIGN.md` (sections 5–7, 10). If code and the doc disagree, ask.

- **Last write wins** by the pair (`client_time`, `session_id`), never arrival time. Later `client_time` wins; equal times go to the greater `session_id`. Removals carry the same pair. A `client_time` missing or more than 15 minutes in the future is clamped to server time.
- **Finished at ≥ 90%** of `videos.duration_seconds` (the client sends no duration). The Lua script evaluates it on every write; a finished video leaves `cw:{user}`. A later event below 90% unfinishes it. A later heartbeat also clears `removed`.
- **Redis keys:** hash `wp:{user}:{video}` (position, `client_time`, `session_id`, flags; no TTL while unflushed, 5 min TTL after a successful flush, the next write clears it); sorted set `cw:{user}` scored by event time (no TTL); sets `wp:dirty` (keys awaiting flush) and `wp:flush-now` (keys to flush ahead of the tick).
- **Atomicity:** one Lua script compares the pair and writes the hash, `cw`, `wp:dirty`, the TTL and, for pause, session end and finishing, `wp:flush-now`. The handler passes the video's duration to it.
- **Flusher:** write-behind; every 30 s read `wp:dirty`, upsert in chunks of 500 rows (one transaction per chunk). After a chunk commits, remove a key from `wp:dirty` and set its TTL only if its stored pair still equals the pair read (atomic compare-and-remove).
- **Immediate flush:** pause and session end (client `reason`), stream close (also abnormal end) and finishing (server-observed). The flusher polls `wp:flush-now` every 5 s. On stream close the handler adds the key with a separate command.
- **Idempotent upsert:** `INSERT … ON CONFLICT (user_id, video_id) DO UPDATE … WHERE (excluded.event_time, excluded.session_id) > (watch_progress.event_time, watch_progress.session_id)`. Replaying a batch is safe. Two uncoordinated flushers are accepted for the demo.
- **PostgreSQL:** `videos` (catalogue and true duration), `user_tokens` (token hash → user ID), `watch_progress` (`user_id, video_id, position_s, duration_s, event_time, session_id, finished, removed, updated_at`; PK `(user_id, video_id)`; partial index `(user_id, event_time DESC)` where not finished and not removed).
- **Crash tolerance:** acknowledge a heartbeat only after the Redis write. A server crash loses no acknowledged heartbeat; a Redis restart loses at most about 1 s (AOF `appendfsync everysec`); losing the Redis instance loses up to about 30 s of unflushed positions (accepted).
- **Redis down:** write straight to PostgreSQL at reduced capacity (same guarded upsert).
- **PostgreSQL down:** keep acknowledging into Redis; dirty keys stay. At the 200 MB cap on `wp:dirty`, writes that would add a new key return `UNAVAILABLE`; writes to keys already in the set still work. Row requests return what Redis has.
- **Row reads:** every `ListContinueWatching` queries PostgreSQL and merges with `cw:{user}` and the hashes; the later pair wins per video; build the full row, then page in memory with a keyset cursor `(event_time, video_id)`. Reads never write to Redis. A `cw:{user}` member whose hash has expired is removed by an atomic script, not a check-then-remove.
- `GetProgress`: position hash first, PostgreSQL if missing; later pair wins; nothing stored → `NOT_FOUND`.
