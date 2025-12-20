# Fast Dev Cycle Guide

This guide documents how to keep the MCP dev URL (for example, https://your-dev-domain.example.com) updated quickly
while minimizing Docker rebuild time. It captures the current baseline timing
and recommended improvements.

## Baseline Timing (Full Rebuild)

Measured on local Docker Desktop (COMPOSE_BAKE disabled, 2025-12-20):

- `docker compose build` total: **~1:21**
- Biggest contributors:
  - Playwright install + OS deps: **~23.5s**
  - Image export/unpack: **~46.5s** + **~8.7s**

This is too slow for tight iteration when only Python code changes.

## Recommended Faster Flow (Low Complexity)

The goal is to keep the existing fast path while avoiding extra maintenance.

### 1) Use the existing server-only rebuild path

For most edits, rebuild only the server image and restart the stack:

```
docker compose build server
docker compose up -d
```

Benefits:
- Avoids full stack rebuilds.
- Keeps dependencies baked in the image (stable).
- Minimizes maintenance surface.

### 2) Enable BuildKit bake (optional)

BuildKit bake can improve layer export speed with no repo changes:

```
COMPOSE_BAKE=true docker compose build server
```

Benefits:
- Better caching and layer reuse.

### 3) Split Playwright into its own layer (optional)

Playwright + system deps add noticeable time. Separate them so standard API dev
builds skip that layer.

Benefits:
- Faster build for normal API work.
- Only pay the Playwright cost when needed (screenshots/contract tests).

### 4) Add a lightweight dev target (optional)

Add a Dockerfile target that excludes heavy deps and Playwright for routine dev.
Use the full target only for CI or screenshot work.

## Suggested Local Commands (Future)

These are recommended helpers we can implement:

- `make dev`: Start stack with bind-mount + reload
- `make dev-build`: Full rebuild
- `make dev-restart`: Restart server container only

## Gotchas

- Contract tests use real MCP providers; they may skip if keys are missing.
- CFPB API data changes; tests should avoid brittle totals unless date ranges
  are fixed.
- If you use the Cloudflare tunnel, ensure the server container has the latest
  code before restarting the tunnel service.

## Next Steps (If You Want Me To Implement)

I can add:
- `docker-compose.override.yml` for dev bind-mounts
- A `Makefile` or `scripts/dev.sh` with the commands above
- A separate Dockerfile target for a lightweight dev build
