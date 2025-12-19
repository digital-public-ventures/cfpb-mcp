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

### E2E Tests Are A Contract (DO NOT CHANGE)

The files under `tests/e2e/` represent a **long-term compatibility contract** with downstream users and third-party agents.

- **DO NOT EDIT `tests/e2e/**`\*\* under any circumstances.
- **DO NOT “fix”, “clean up”, “refactor”, “rename”, “reformat”, or “improve”** E2E tests.
- If behavior changes require a new contract, **add a new suite** (e.g. `tests/e2e_v2/`) rather than modifying the existing E2E tests.
- If an E2E test fails after server changes, treat it as a **regression in the server/public contract**, not a reason to modify the E2E tests.

## Commit & Pull Request Guidelines

- **Commits**: Use concise, imperative messages (e.g., "Add trends parameter validation"); group logical changes per commit.
- **PRs**: Provide a clear summary, linked issue (if any), test results, and notes on REST/MCP interface impacts. Add curl examples or screenshots when modifying responses.

## Security & Configuration Tips

- **Secrets**: No secrets or API keys belong in code or history; rely on public CFPB endpoints only.
- **Config overrides**: Prefer environment variables for future tunables (e.g., alternate base URLs); avoid hardcoding local paths.
- **Operational hygiene**: Keep long-running clients within the shared `httpx.AsyncClient`; clean up resources to prevent connection leaks.
