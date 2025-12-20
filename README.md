# CFPB MCP + REST Hybrid Server

One FastAPI app that serves:

* **MCP protocol** at `/mcp` (Streamable HTTP) and `/mcp/sse` (legacy SSE for Claude Desktop)
* **REST API** at `/search`, `/trends`, etc. (for ChatGPT Actions)

## Developer docs

* `docs/testing.md` — test strategy, markers, and gotchas
* `docs/dev-cycle.md` — faster dev loop guidance for Docker + tunnel

Preferred dev loop (fast rebuild + restart):

```
docker compose build server
docker compose up -d
```

Optional BuildKit speed-up:

```
COMPOSE_BAKE=true docker compose build server
```

## Run locally

```bash
cd /Users/jim/cfpb-mcp
uv venv
uv sync
uv run python server.py
```

Server will listen on `http://localhost:8000`.

* OpenAPI schema: `http://localhost:8000/openapi.json`
* Docs UI: `http://localhost:8000/docs`

## Run with Docker (server + Postgres)

This repo includes a Docker Compose stack:

* FastAPI server exposed at `http://localhost:8002`
* Postgres (pgvector base) exposed at `localhost:5433` (optional; used in later phases)

```bash
docker compose up --build
```

OpenAPI schema: `http://localhost:8002/openapi.json`

## Claude Desktop (MCP)

Preferred: install the packaged Claude Desktop extension (`.mcpb`).

1. Build (or download) one of:
   * `deployment/anthropic/mcpb/dist/cfpb-complaints.dev.mcpb` (defaults to `http://localhost:8000/mcp/sse`)
   * `deployment/anthropic/mcpb/dist/cfpb-complaints.prod.mcpb` (defaults to the deployed server)
2. In Claude Desktop: Settings → Extensions → drag the `.mcpb` file in.
3. Configure the “Server URL” if needed (you can paste either a base URL or an `/mcp/sse` URL).

Important: if you previously added a manual `mcpServers.cfpb-complaints` entry (the legacy `npx mcp-remote ...` approach), remove it.
Otherwise Claude will keep launching `npx` (and may restart-loop if the URL is unreachable), instead of running the bundled extension shim.

Debugging pointers (macOS):

* Logs: `~/Library/Logs/Claude/mcp-server-*.log`
* If you see a line like `Using MCP server command: .../npx -y mcp-remote ...`, you are running the legacy config.
* If you see lines starting with `[CFPB MCPB]`, you are running the `.mcpb` shim.

### Optional: protect `/mcp/*` with an API key

If you expose this server publicly (e.g., via Cloudflare Tunnel), you can require an API key for all MCP endpoints.

Set:

* `CFPB_MCP_API_KEYS` — comma-separated allowed keys (example: `key1,key2`)

Generate a new key (hex) with a one-liner:

* Python: `python -c "import secrets; print(secrets.token_hex(32))"`
* OpenSSL: `openssl rand -hex 32`

Both commands generate a 64-character hex string (32 random bytes).

Optional rate limiting (applies to all `/mcp/*` requests, per key):

* `CFPB_MCP_RATE_LIMIT_RPS` — refill rate (requests/sec)
* `CFPB_MCP_RATE_LIMIT_BURST` — burst capacity (tokens)

Clients must send `X-API-Key: <key>` on `/mcp/sse` and `/mcp/messages`.

### Prereq: Cloudflare Tunnel dashboard checklist (Phase 5.2)

If you want Claude to connect to this MCP server over a stable public HTTPS URL (e.g. a Custom Connector), this repo’s intended path is a **Cloudflare Tunnel** managed in the Cloudflare dashboard (token-based).

You will do these steps in Cloudflare (one-time):

1. **Cloudflare setup**
   * Your domain is onboarded to Cloudflare (nameservers pointing to Cloudflare).
   * You can create Zero Trust tunnels (Cloudflare Zero Trust enabled for your account).

2. **Create a tunnel**
   * Cloudflare Dashboard → Zero Trust → Networks → Tunnels
   * Create tunnel (type: **Cloudflared**) with a name like `cfpb-mcp`.
   * Copy the **connector token** (this becomes `TUNNEL_TOKEN`). Treat it like a secret.

3. **Add a Public Hostname route**

   * In that tunnel, add a Public Hostname:
     * Hostname: `cfpb-mcp.jimmoffet.me` (or your hostname)
     * Service type: **HTTP**
     * URL: `http://server:8000`

   Notes:

   * `server` is the Docker Compose service name in this repo’s `docker-compose.yml`.
   * `8000` is the container port uvicorn listens on.
   * With this setup, you typically do **not** need to publish a host port for public access; the tunnel runs inside the Compose network.

4. **(Recommended) Lock down the endpoint**
   * Set `CFPB_MCP_API_KEYS` and use `X-API-Key` in the Claude connector header configuration.

After that, when the tunnel is running, your connector URL is:

* `https://cfpb-mcp.jimmoffet.me/mcp/sse`

And Claude will also need to reach:

* `https://cfpb-mcp.jimmoffet.me/mcp/messages`

## ChatGPT Actions (REST)

### One-command dev with ngrok

If you want a public URL (useful for the Actions UI), this repo includes a small helper that runs the server and ngrok together:

```bash
uv run python scripts/dev_with_ngrok.py
```

It will print a public URL plus the corresponding `/openapi.json` URL.

Prereqs:

1. Install ngrok: https://ngrok.com/download
2. Authenticate once: `ngrok config add-authtoken <YOUR_TOKEN>`

### Manual ngrok

1. Expose your server (e.g. `ngrok http 8000`).
2. In the Actions UI, point to `https://<your-host>/openapi.json`.

## Quick curl smoke tests

```bash
curl "http://localhost:8000/search?size=3"
curl "http://localhost:8000/trends?trend_depth=3"
curl "http://localhost:8000/geo/states"
curl "http://localhost:8000/suggest/company?text=bank&size=5"
```
 
