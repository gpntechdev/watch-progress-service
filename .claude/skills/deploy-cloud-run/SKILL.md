---
name: deploy-cloud-run
description: Use when building Docker images, writing CI, or deploying to Google Cloud Run.
---

# Deploy conventions

- Flow: Docker build → push to Artifact Registry (keep one or two small images) → deploy to Cloud Run.
- Cloud Run flags: **instance-based billing** (so the background flusher isn't CPU-throttled), **HTTP/2 end-to-end** (gRPC needs it), **max instances 2**, scale to zero, Envoy as a sidecar container.
- Secrets in Secret Manager: `DATABASE_URL` and `REDIS_URL`. Never in the repo or image. The demo tokens are public by design (the browser sends them) and are documented in the README; only their hashes are stored.
- Run `seed-demo` (few fixed users, videos) on deploy. **Never run `seed-loadtest` against the cloud**; it must refuse non-local database URLs.
- Cloud Run's request timeout caps a long stream; `StreamProgress` has a 55 minute deadline (assumes a 60 minute maximum; verify).
- Set a Google Cloud budget alert at $5 **before the first deploy**.
- GitHub Actions: lint, test, `buf breaking`, then deploy. Deploy steps live in `deploy/` and `.github/workflows/`.
- Managed data: Neon Free (PostgreSQL), Upstash Free (Redis, which counts REST and protocol commands; the free monthly limit is used in minutes at load-test rates). Free-tier limits change; re-check pricing pages before deploying.
- **Never load-test the cloud demo.**
