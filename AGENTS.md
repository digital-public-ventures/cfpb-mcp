## Agent Handbook

### CLI guardrails

* Avoid terminal heredocs (`cat <<EOF`, `python - <<'PY'`); they crash this shell.
* Write helper scripts under `temp/` and run them normally (e.g., `bash temp/diagnose.sh`).
* Prefer simple pipelines/one-liners for quick commands.

### Repository map

* `server.py`: FastAPI app exposing REST + MCP; shared logic lives near the top.
* `tests/`: Pytest suite that boots uvicorn in-process for REST/MCP flows (`test_rest_*`, `test_mcp_*`).
* `scripts/`: Local harnesses for MCP/OpenAPI clients and dev helpers.
* `docs/`: Integration notes and examples; keep in sync with interface changes.
* `deployment/`: Packaging for MCP extensions (e.g., `.mcpb`) and deployment assets.
* `planning/`: Design notes and task planning artifacts.
* `README.md` / `IDEA.md`: Quickstart + design context; update when workflows change.

### Roadmap snapshot (see `planning/ROADMAP.md`)

* Complete: Phase 1 (REST+MCP wrapper), Phase 2 (Docker Compose stack), Phase 4 (proxy analytics helpers), Phase 5.2 (Cloudflare tunnel for remote MCP).
* In flight/next: Phase 3 proxy hardening, Phase 5.3 FastMCP migration with dual transports, Phase 5.4 OAuth for Claude connectors, Phase 5.5 cleanup of legacy `.mcpb`/API key paths, Phase 6 local dataset + vector search.

### Dev commands

* Create env & install: `uv venv && uv sync`
* Run server locally: `uv run python server.py` (listens on `http://localhost:8000`)
* REST smoke checks: `curl "http://localhost:8000/search?size=3"` (see README for more)
* Run all tests: `uv run pytest`
* Focused test: `uv run pytest tests/test_rest_endpoints.py -k search_smoke`
* MCP harness: `uv run python scripts/anthropic_mcp_harness.py`
* MCP endpoints: Streamable HTTP at `/mcp`, legacy SSE at `/mcp/sse`

### Coding style

* Python 3.10+, PEP 8, 4-space indentation.
* Prefer explicit type hints and `Optional`/`Literal` as used in `server.py`.
* Keep shared logic transport-agnostic; reuse helpers across REST and MCP tools.
* Keep `server.py` per-file ignores minimal and documented in `ruff.toml`.
* Prefer narrow exception handling; reserve broad `Exception` for best-effort cleanup.

### Testing expectations

* Pytest + pytest-asyncio; fixtures spin up uvicorn (`client`, `server_url`).
* Favor small payload sizes (e.g., `size=1`) to limit API load.
* Live CFPB API dependency means data can vary; keep assertions resilient.
* Run `uv run pytest` (plus targeted cases) before merging.

### Contract tests (prompt + assertions only)

The files under `tests/contract/` represent a **long-term compatibility contract** with downstream users and third-party agents.

The only sacred parts of the contract are:

User prompt (quoted exactly):
"I'm researching CFPB consumer complaints about loan forbearance. Please find a complaint mentioning 'forbearance' where the company name is present, then tell me the complaint id, the company (if present), the state (if present), and a short 2-3 sentence summary grounded in the complaint. If you can't use tools, say 'MCP tools unavailable'."

Assertions (quoted exactly):

Anthropic contract assertions:
- "Final response text is non-empty."
- "\"MCP tools unavailable\" is not present in the final response text."
- "A complaint id is obtained via tools."
- "The complaint id is 4-9 digits long."
- "The tool-derived complaint id appears in the final response text."
- "The complaint id parsed from text matches the tool-derived complaint id."
- "The first word of the complaint company appears in the final response text (case-insensitive)."

OpenAI contract assertions:
- "Final response text is non-empty."
- "\"MCP tools unavailable\" is not present in the final response text."
- "A complaint id is obtained via tools."
- "The complaint id is 4-9 digits long."
- "A 4-9 digit complaint id token can be extracted from the final response text."
- "If the tool-derived complaint id appears in the final response text, it matches the extracted complaint id."
- "The first word of the complaint company appears in the final response text (case-insensitive)."

We may add another user prompt and its own assertions to the contract in the future.

### Git workflow

* Work on feature branches, not `main` (e.g., `phase5.2/mcp-auth`).
* Keep PRs small and focused; include concise summaries and test output.
* Use concise, imperative commits (e.g., "Add trends parameter validation").

### Security & operations

* Do not commit secrets; rely only on public CFPB endpoints.
* Prefer env vars for tunables (e.g., alternate base URLs); avoid hardcoded local paths.
* Keep long-running clients within the shared `httpx.AsyncClient` and clean up resources.

### Cloudflare tunnel (Phase 5.2)

Two supported approaches:

1. Token-based (default): set `TUNNEL_TOKEN` in `.env`; config managed in Cloudflare dashboard.
2. File-based: set `TUNNEL_ID` in `.env` and mount `./cloudflared/` with `credentials.json` and `config.yml`.
