# CFPB MCP (Python + TypeScript)

This repo contains two implementations of the CFPB MCP server:

- `py-mcp`: FastAPI app serving MCP + REST.
- `ts-mcp`: Cloudflare Workers TypeScript MCP server (Streamable HTTP).

The shared `.env` lives at the repo root.

## Python server (`py-mcp`)

Developer docs:

- `py-mcp/docs/testing.md` — test strategy, markers, and gotchas
- `py-mcp/docs/dev-cycle.md` — faster dev loop guidance for Docker + tunnel

Run locally:

```bash
cd py-mcp
uv venv
uv sync
uv run python src/server.py
```

Server will listen on `http://localhost:8000`.

- OpenAPI schema: `http://localhost:8000/openapi.json`
- Docs UI: `http://localhost:8000/docs`

Run tests:

```bash
cd py-mcp
uv run pytest -rs
```

Linting + formatting:

```bash
cd py-mcp
uvx ruff check .
uvx ruff format .
uvx pyright
```

Run with Docker (server + Postgres):

```bash
cd py-mcp
docker compose up --build
```

OpenAPI schema: `http://localhost:8002/openapi.json`

## TypeScript worker (`ts-mcp`)

Install + run locally:

```bash
cd ts-mcp
npm install
npm run dev
```

Run tests:

```bash
cd ts-mcp
npx vitest run
```

Linting + formatting:

```bash
cd ts-mcp
npx biome check .
npx biome format --write .
```

Cloudflare deploy (versions upload from repo root):

```bash
./scripts/wrangler_versions_upload.sh
```

## MCP API keys and rate limits

Both implementations can require API keys on `/mcp`.

Set:

- `CFPB_MCP_API_KEYS` — comma-separated allowed keys (example: `key1,key2`)

Generate a new key (hex) with:

- Python: `python -c "import secrets; print(secrets.token_hex(32))"`
- OpenSSL: `openssl rand -hex 32`

Optional rate limiting:

- `CFPB_MCP_RATE_LIMIT_RPS` — refill rate (requests/sec)
- `CFPB_MCP_RATE_LIMIT_BURST` — burst capacity (tokens)
