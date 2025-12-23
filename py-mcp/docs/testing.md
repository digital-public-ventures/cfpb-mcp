# Testing Strategy

This repo relies on a layered testing approach that balances fast feedback with
live API coverage. Some suites hit public CFPB endpoints and MCP providers, so
the tests are designed to be resilient to data drift while still asserting core
behavior.

## Test Suites and Markers

- `fast`: Low-latency tests intended for frequent runs. These include pure
  mapping/validation unit-style checks and contract tests that are quick to
  execute.
- `integration`: Exercises the local FastAPI + MCP server and makes live CFPB
  API calls. These validate our REST + MCP interface behavior.
- `slow`: Any heavier tests (browser, long network hops) that should be run
  less frequently. Currently minimal, but reserved for heavier checks.
- `extra_slow`: Long-running tests or heavier permutations that you may want
  to skip during regular iteration.
- `contract`: Immutable public contract tests (prompt + assertions). These
  protect MCP tool-loop guarantees and are marked `fast`.

Default `pytest` runs include everything; individual suites use markers.

## Recommended Commands

- Full suite: `uv run pytest`
- Fast suite: `uv run pytest -m fast`
- Integration suite: `uv run pytest -m integration`
- Contract suite: `uv run pytest -m contract`
- Slow suite: `uv run pytest -m slow`
- Scripted helper: `python scripts/run_tests.py [unit|integration|slow|contract|full]`

## Linting & Formatting

We use Ruff for both linting and formatting. Configuration lives in `ruff.toml`
and is shared by pre-commit, local editor settings, and future CI.

Common commands:

- Lint: `uv run ruff check .`
- Auto-fix: `uv run ruff check . --fix`
- Format: `uv run ruff format .`

Pre-commit:

- Install hooks: `uv run pre-commit install`
- Run all hooks: `uv run pre-commit run --all-files`

## Code Quality Guardrails

- Keep `server.py` per-file ignores minimal and documented in `ruff.toml`.
- Prefer narrow exceptions; only use broad `Exception` handling for best-effort cleanup.
- For API payloads where strict typing is impractical, explain the `Any` usage with nearby comments or docstrings.
- Run the server checks when editing `server.py`:
  - `uv run ruff check server.py`
  - `uv run pyright server.py`
- For deeper diagnostics (writes to `temp/output/` and applies fixes), use:
  - `python temp/scripts/dump_diagnostics.py server.py`

## Contract Tests (Why They Exist)

The contract tests in `tests/contract/` verify a fixed prompt against fixed assertions.
This protects the external user experience of MCP tool loops. The prompt and assertions are
documented in `claude.md`, `AGENTS.md`, and `.github/copilot-instructions.md`.

If behavior changes require a new prompt or assertions, add a new contract test
alongside the existing one; do not modify existing contract tests without
explicitly updating the contract documentation.

## Known Gotchas

- Live CFPB API data changes. Prefer resilient assertions, especially in
  integration tests. Avoid hardcoding totals unless you are already applying
  a fixed date window.
- The CFPB UI defaults to an implicit date window when dates are omitted. Our
  deeplink mapping code now explicitly sets `date_received_min` and
  `date_received_max` to keep UI/API parity stable.
- Contract tests require third-party API keys (Anthropic/OpenAI). If the keys
  are missing or the model declines tool usage, the test may skip or fail.
- Tests spin up uvicorn in-process via `tests/conftest.py`. If a local server is
  already running, it can be reused via `TEST_SERVER_URL`.

## When Tests Fail

- Integration failures: check for CFPB upstream variability or rate limits.
- Contract failures: treat as a public contract regression; update tooling or
  add a new contract rather than changing the existing one.
- Flaky UI/network issues: re-run with a smaller `size` or narrower date
  window to reduce API load.
