---
name: web-player-client
description: Use when working in web/ (player, Continue watching row, generated client).
---

# Web client conventions

- Use the generated client in `web/src/gen/` with `@connectrpc/connect-web` and the **gRPC-Web transport**. Never hand-write request types.
- Browsers can't do client streaming: report with unary `ReportProgress`.
- Report timing: every 5 s while playing, and immediately on pause, seek and tab hide (`visibilitychange`).
- Use TanStack Query for the "Continue watching" row; invalidate it after a report or remove.
- The user comes from the demo token sent as auth metadata, not from the request body.
- Accessibility checklist (player and row): everything keyboard-operable with visible focus; buttons have accessible names; progress bars use `role="progressbar"` with `aria-valuenow/min/max` and a label; the remove action is announced and focus moves sensibly after removal; captions/controls don't rely on colour alone.
- Do not edit `web/src/gen/`; change the proto instead (see `proto-api`).
