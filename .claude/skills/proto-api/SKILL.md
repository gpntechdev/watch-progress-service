---
name: proto-api
description: Use when adding or changing an RPC or message in proto/watchprogress/v1/watch_progress.proto.
---

# Changing the API

1. Edit only `proto/watchprogress/v1/watch_progress.proto`. Never edit generated code.
2. Follow Google API style (AIP): `VerbNoun` RPC names, a request and response message per RPC (`FooRequest` / `FooResponse`), `snake_case` fields.
3. Lists paginate with `page_size` and an opaque `page_token` / `next_page_token` (AIP-158).
4. Field numbers are never reused or renumbered. Remove a field with `reserved`, never by reusing its number.
5. Run `buf lint`, then `buf breaking --against '.git#branch=main'`. A breaking change needs an explicit reason from the owner.
6. Run `make gen` to regenerate Python and TypeScript.
7. Update both sides: the servicer in `server/` and the client use in `web/`. Add or update tests.

The user ID is never a request field; it comes from auth metadata.
