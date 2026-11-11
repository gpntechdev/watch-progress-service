---
name: proto-api
description: Use when adding or changing an RPC or message in proto/watchprogress/v1/watch_progress.proto.
---

# Changing the API

Source of truth: `docs/DESIGN.md` section 4 and the sketch in `docs/PLAN.md`.

1. Edit only `proto/watchprogress/v1/watch_progress.proto`. Never edit generated code.
2. Follow Google API style (AIP): `VerbNoun` RPC names, a request and response message per RPC (`FooRequest` / `FooResponse`), `snake_case` fields. Enums have a `PROGRESS_REASON_`-style prefix and a zero value `..._UNSPECIFIED`.
3. Lists paginate with `page_size` (default 25, max 100) and an opaque `page_token` / `next_page_token` (AIP-158).
4. Field numbers are never reused or renumbered once released. Remove a field with `reserved`.
5. Run `buf lint`, then `buf breaking --against '.git#branch=main'`. A breaking change needs an explicit reason from the owner.
6. Run `make gen` to regenerate Python and TypeScript.
7. Update both sides: the servicer in `server/` and the client use in `web/`. Add or update tests.

Contract facts: `ProgressEvent` carries `video_id`, `position_seconds`, `client_time`, `session_id` and `reason` (periodic, pause, seek, tab hidden, session end); it has no duration (the server uses `videos`). `RemoveFromContinueWatching` carries `client_time` and `session_id`. The user ID is never a request field; it comes from auth metadata.
