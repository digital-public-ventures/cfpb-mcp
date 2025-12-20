# IMPORTANT: Terminal heredocs (e.g. `cat <<EOF ... EOF`, `python3 - <<'PY' ... PY`) are not allowed.

# They consistently fail in this environment and can crash/restart the shell.

#

# Instead:

# - Use the workspace file tools to write any script into `temp/` (e.g. `temp/diagnose.sh`).

# - Then run it with a normal terminal command (e.g. `bash temp/diagnose.sh`).

# - Prefer piping simple one-liners directly (no heredocs) or saving them as scripts.

# Repository Guidelines

## Project Structure & Module Organization

- **`server.py`**: Single FastAPI app exposing both REST routes and MCP tools; shared business logic lives in helper functions near the top of the file.
- **`tests/`**: Pytest suite that boots uvicorn in-process and exercises REST and MCP flows (`test_rest_*`, `test_mcp_*`).
- **`scripts/`**: Local harnesses for MCP/OpenAPI clients; useful for manual smoke checks.
- **`docs/`**: Notes and examples for MCP integrations; keep in sync with any interface changes.
- **`README.md` & `IDEA.md`**: Quickstart and design context; update when changing developer workflows.

## Build, Test, and Development Commands

- **Create env & install**: `uv venv && uv sync`
- **Run server locally**: `uv run python server.py` (listens on `http://localhost:8000`)
- **REST smoke checks**: `curl "http://localhost:8000/search?size=3"` (see README for more)
- **Run all tests**: `uv run pytest`
- **Focused test example**: `uv run pytest tests/test_rest_endpoints.py -k search_smoke`
- **Optional harnesses**: `uv run python scripts/anthropic_mcp_harness.py` to exercise MCP tools interactively.

## Coding Style & Naming Conventions

- **Language**: Python 3.10+, PEP 8 style, 4-space indentation.
- **Types**: Prefer explicit type hints and `Optional`/`Literal` usage as seen in `server.py`.
- **Naming**: Snake_case for functions/vars; keep REST paths and MCP tool names descriptive and aligned.
- **Structure**: Keep shared logic transport-agnostic; REST endpoints and MCP tools should reuse the same helper functions.

## Testing Guidelines

- **Frameworks**: Pytest + pytest-asyncio; fixtures spin up a temporary uvicorn server (`client`, `server_url`).
- **Scope**: Write `test_*.py` files alongside existing suites; prefer small payload sizes (`size=1`) to reduce API load.
- **External dependency**: Tests hit the public CFPB API; ensure network access and expect live data variability.
- **Before PRs**: Run `uv run pytest` and relevant targeted cases.

### Contract Tests (Prompt + Assertions Only)

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

## Commit & Pull Request Guidelines

## Git Workflow (IMPORTANT)

- **Do not do feature work directly on `main`.** Always create a feature branch for each phase/feature/bugfix.
- **Branch naming:** Prefer `phase<phase-number>/<short-slug>` (examples: `phase5.2/mcp-auth`, `phase5.2/cloudflare-docs`, `phase1/rest-search-tuning`).
- **Before merging to `main`:** Run `uv run pytest` (and any relevant targeted tests) and ensure results are acceptable.
- **Integration path:** Open a PR from the feature branch to `main`, include a concise summary + test output, and only merge after review/testing.
- **Small, reviewable PRs:** Keep changes focused; split unrelated work into separate branches/PRs.

- **Commits**: Use concise, imperative messages (e.g., "Add trends parameter validation"); group logical changes per commit.
- **PRs**: Provide a clear summary, linked issue (if any), test results, and notes on REST/MCP interface impacts. Add curl examples or screenshots when modifying responses.

## Security & Configuration Tips

- **Secrets**: No secrets or API keys belong in code or history; rely on public CFPB endpoints only.
- **Config overrides**: Prefer environment variables for future tunables (e.g., alternate base URLs); avoid hardcoding local paths.
- **Operational hygiene**: Keep long-running clients within the shared `httpx.AsyncClient`; clean up resources to prevent connection leaks.

### Cloudflare Tunnel Configuration

Two approaches supported (choose one):

1. **Token-based (default):** Set `TUNNEL_TOKEN` in `.env` - tunnel config managed via Cloudflare dashboard
2. **File-based (config-as-code):** Set `TUNNEL_ID` in `.env` and mount `./cloudflared/` with credentials.json and config.yml
