# CFPB MCP + REST Hybrid Server

One FastAPI app that serves:

* **MCP protocol** at `/mcp` (for Claude Desktop)
* **REST API** at `/search`, `/trends`, etc. (for ChatGPT Actions)

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

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cfpb-complaints": {
      "url": "http://localhost:8000/mcp/sse",
      "type": "sse"
    }
  }
}
```

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
