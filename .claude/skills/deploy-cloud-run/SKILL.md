---
name: deploy-cloud-run
description: Use when building Docker images, writing CI, or deploying to Google Cloud Run.
---

# Deploy conventions

- Flow: Docker build → push to Artifact Registry (keep one or two small images) → deploy to Cloud Run.
- Cloud Run flags: **instance-based billing** (so the background flusher isn't CPU-throttled), **HTTP/2 end-to-end** (gRPC needs it), **max instances 2**, scale to zero, Envoy as a sidecar container.
- Secrets (tokens, `DATABASE_URL`, `REDIS_URL`) come from Secret Manager, never from the repo or image.
- Set a Google Cloud budget alert at $5 **before the first deploy**.
- GitHub Actions: lint, test, `buf breaking`, then deploy. Deploy steps live in `deploy/` and `.github/workflows/`.
- Managed data: Neon Free (PostgreSQL), Upstash Free (Redis). Free-tier limits change; re-check pricing pages before deploying.
- **Never load-test the cloud demo.**
