---
name: web-player-client
description: Use when working in web/ (player, Continue watching row, generated client).
---

# Web client conventions

Source of truth: `docs/DESIGN.md` section 4.

- Use the generated client in `web/src/gen/` with `@connectrpc/connect-web` and the **gRPC-Web transport**. Never hand-write request types.
- Browsers can't do client streaming: report with unary `ReportProgress`, with a 5 s deadline on every call.
- Report timing, each with its `reason`: every 5 s while playing (periodic); on pause (pause); on seek, throttled (seek); on `visibilitychange` to hidden (tab hidden); when the playback session ends (session end). Pause and session end are flushed to PostgreSQL immediately.
- Send `client_time` and a `session_id` that stays the same for one playback session. Do not send a duration.
- Videos are plain files (HTML5 `<video>`); URLs come from the `videos` data. The host must support range requests.
- Use TanStack Query for the "Continue watching" row; invalidate it after a report or remove.
- Treat `NOT_FOUND` on `RemoveFromContinueWatching` as success (a retried removal). Do not retry `RESOURCE_EXHAUSTED` in a tight loop (limit is 40 requests per minute per user).
- The demo token is public (it is visible in the browser); it is sent as auth metadata, never in the request body.
- Accessibility checklist (player and row): everything keyboard-operable with visible focus; buttons have accessible names; progress bars use `role="progressbar"` with `aria-valuenow/min/max` and a label; the remove action is announced and focus moves sensibly after removal; captions/controls don't rely on colour alone.
- Do not edit `web/src/gen/`; change the proto instead (see `proto-api`).
