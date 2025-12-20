# Phase 5.2 Plan — Claude Custom Connector via Cloudflare Tunnel

**Goal:** Let Claude (Desktop/Web/Mobile) connect **directly** to our MCP server over **HTTPS** (SSE) without a local `.mcpb` extension.

**Approach:** Use **Cloudflare Tunnel** to expose the existing local FastAPI + MCP SSE endpoint (`/mcp/sse`) as a stable `https://...` URL, and add a small **authentication layer** + basic **rate limiting/auditing** on the server.

***

## Why Cloudflare Tunnel

* Provides **public HTTPS** termination (TLS) in front of a locally-running server.
* Avoids having to deploy to a cloud VM immediately.
* Good for **dev/demo** and early pilot validation of “remote-first connector” behavior.

**Caveat:** A tunnel makes your local machine a public service. Treat this as a controlled pilot path with strong auth, logging, and a kill switch.

***

## Scope / Non-Goals

**In scope (Phase 5.2 MVP):**

* Remote MCP endpoint over HTTPS: `https://<hostname>/mcp/sse`
* Authentication (API key header)
* Basic request logging/auditing
* Light rate limiting (per-key)
* Documentation for Claude connector registration

**Out of scope (later hardening):**

* OAuth
* Multi-tenant isolation beyond per-key limits
* Full SIEM-grade audit pipeline

***

## Requirements Mapping (from ROADMAP Phase 5.2)

* **HTTPS deployment:** provided by Cloudflare Tunnel
* **Authentication:** implement API key header validation
* **Public internet accessibility:** tunnel hostname is public
* **Rate limiting / tenant isolation:** per-API-key throttles + (optional) per-key prefixes
* **Stability:** deterministic JSON, explicit error objects, concurrency-safe httpx client (already present)

***

## Proposed Client Contract

### MCP endpoint

* **SSE:** `GET https://<hostname>/mcp/sse`
* **Messages:** `POST https://<hostname>/mcp/messages`

### Auth header

* `X-API-Key: <secret>`

(We should keep it simple and explicit. Claude connector UIs typically support setting request headers.)

***

## Implementation Steps

### 1) Cloudflare Tunnel setup

This repo’s preferred approach is a **dashboard-managed, token-based** Cloudflare Tunnel running as a **Docker Compose** service.

**You’ll do in the Cloudflare dashboard (coordination item):**

In Cloudflare Dashboard → Zero Trust → Tunnels:

1. Create a tunnel (type: **Cloudflared**), e.g. `cfpb-mcp`.
2. Add a **Public Hostname**:

* Hostname: `cfpb-mcp.jimmoffet.me`
* Service type: **HTTP**
* URL: `http://server:8000`

Notes:

* `server` is the Docker Compose service name in this repo’s current `docker-compose.yml`.
* We target the container port `8000` on the internal Compose network; no public host port is required for the tunnel.

**We’ll do in this repo (Compose runtime):**

Add a `cloudflared` service (image `cloudflare/cloudflared:latest`) that runs `tunnel run` with `TUNNEL_TOKEN`.
Example shape (service name and target must match the dashboard hostname mapping above):

```yaml
cloudflared:
  image: cloudflare/cloudflared:latest
  restart: unless-stopped
  command: tunnel run
  environment:
   - TUNNEL_TOKEN=${TUNNEL_TOKEN}
  depends_on:
   - server
```

**Result:** `https://cfpb-mcp.jimmoffet.me/mcp/sse` proxies to the internal server.

> Optional alternative (not the default): file-managed tunnel config (`TUNNEL_ID` + `cloudflared/config.yml` + `credentials.json`). Do not mix token-based and file-managed modes.

***

### 2) Add API-key auth to the MCP endpoints

We need to protect **both**:

* `GET /mcp/sse`
* `POST /mcp/messages`

**Design choice:**

* Validate `X-API-Key` in FastAPI middleware or dependency.
* Reject unauthenticated calls with a deterministic JSON error:

```json
{"error": {"type": "auth", "message": "Missing or invalid API key"}}
```

**Env vars:**

* `CFPB_MCP_API_KEYS` (comma-separated)
  * example: `CFPB_MCP_API_KEYS=dev-abc123,dev-def456`

**Acceptance criteria:**

* Without header → 401
* With wrong key → 401
* With valid key → normal behavior

***

### 3) Rate limiting

Minimal viable approach:

* In-memory token bucket keyed by API key.
* Env vars:
  * `CFPB_MCP_RATE_LIMIT_RPS` (default e.g. 2)
  * `CFPB_MCP_RATE_LIMIT_BURST` (default e.g. 5)

Return deterministic 429:

```json
{"error": {"type": "rate_limit", "message": "Too many requests"}}
```

***

### 4) Audit logging

Log at least:

* timestamp
* API key hash prefix (never log the full key)
* endpoint (`/mcp/sse` or `/mcp/messages`)
* tool name + arguments (for messages)
* response status / duration

Implementation note:

* Use structured JSON lines to stderr (works in containers/tunnel logs):
  * `print(json.dumps({...}), file=sys.stderr)`

***

### 5) Claude Connector registration

In Claude’s **Connectors** UI:

* Connector type: Remote MCP / Custom Connector
* URL: `https://cfpb-mcp.jimmoffet.me/mcp/sse`
* Headers:
  * `X-API-Key: <your-key>`

**Validation:**

* Claude can list tools and call `search_complaints` successfully.

***

## Operational Checklist

* Rotate API key immediately if leaked.
* Kill switch:
  * Stop `cloudflared` process
  * (Optional) remove DNS route
* Confirm server listens on `127.0.0.1` only (tunnel is the only ingress).

***

## Smoke Tests

1. SSE reachability (should be 200 + `text/event-stream`):

```bash
curl -i \
  -H 'Accept: text/event-stream' \
  -H 'X-API-Key: <key>' \
  'https://cfpb-mcp.jimmoffet.me/mcp/sse'
```

2. Messages endpoint should exist:

```bash
curl -i \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <key>' \
  -d '{}' \
  'https://cfpb-mcp.jimmoffet.me/mcp/messages'
```

3. Negative auth:

```bash
curl -i 'https://cfpb-mcp.jimmoffet.me/mcp/sse'
# expect 401
```

***

## Risks / Gotchas

* **Claude sees 200 on `/mcp/sse` but still “can’t connect”** often means:
  * `/mcp/messages` isn’t reachable (blocked by auth/misrouting)
  * Auth header not configured in connector
  * Tunnel/proxy strips headers (verify with server-side logs)

* Cloudflare’s edge may buffer/proxy differently; ensure:
  * SSE responses are not compressed in a way that breaks streaming
  * Keep-alives are enabled

***

## Deliverables (this phase)

* Server: API-key auth + rate limiting + audit logging on MCP routes
* Docs: connector setup instructions + Cloudflare tunnel guide
* Optional: a `scripts/cloudflare_tunnel_setup.md` quickstart

***

## Next steps (post-Phase 5.2)

* Replace API key auth with OAuth for production.
* Multi-tenant isolation (per-key quotas, separate data policies).
* Deploy server to a real runtime (Fly.io/Render/K8s) and keep tunnel only for dev.
