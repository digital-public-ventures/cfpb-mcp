# Gemini Agent Best Practices

This document outlines the operational best practices for Gemini agents working on the `cfpb-mcp` project. Adherence to these guidelines ensures consistency, stability, and alignment with the project's roadmap.

## 1. Project Context & Roadmap

- **Current Phase:** Phase 5.3 (FastMCP Standardization).
- **Core Goal:** Build a semantic bridge to the CFPB complaint database, prioritizing intelligence over simple API wrapping.
- **Architecture:** The server supports dual transports:
    - **MCP:** For AI assistants (Claude, etc.).
    - **REST/OpenAPI:** `POST /mcp` (Streamable HTTP) and `GET /mcp/sse` (Legacy SSE).
- **Roadmap:** Consult `planning/ROADMAP.md` before starting any major task. Future work includes OAuth (Phase 5.4) and Vector Search (Phase 6).

## 2. Environment & Dependency Management

We use `uv` for all Python environment and dependency management.

- **Virtual Environment:** Ensure `uv` manages the `.venv`.
- **Sync Dependencies:** Run `uv sync` to ensure your environment matches `uv.lock`.
- **Run Commands:** Use `uv run <command>` (e.g., `uv run pytest`, `uv run python server.py`).
- **Add Dependencies:** Use `uv add <package>` to update `pyproject.toml` and `uv.lock`.

## 3. Git Workflow

- **Branching Strategy:**
    - Create a new branch for each specific task or phase of work.
    - Naming convention: `feat/phase-x-y-description` or `fix/issue-description`.
    - Example: `feat/phase-5-3-fastmcp-migration`.
- **Commits:**
    - Use Conventional Commits (e.g., `feat: ...`, `fix: ...`, `docs: ...`).
    - Keep commits atomic and focused.
- **Pull Requests/Merging:**
    - Do not merge your own branches without explicit user approval.
    - Wait for instruction before merging into `main`.

## 4. Coding Standards

- **Defensive Coding:** The upstream CFPB API is sensitive to `null` or empty string parameters. Always prune these from dictionaries before making requests to avoid 400 errors.
- **Architectural Invariants:**
    - Changes must support *both* MCP and REST/OpenAPI interfaces.
    - Shared logic should be transport-agnostic.
- **Testing:**
    - **Immutable Contracts:** The `tests/e2e` suite represents public contracts. Do not modify these tests to make breaking changes pass.
    - **New Features:** Add new test suites for new functionality.
    - **Running Tests:** `uv run pytest`.

## 5. Documentation

- **Update Docs:** Keep `docs/` up-to-date with code changes.
- **URL Construction:** Refer to `docs/CFPB_UI_URL_CONSTRUCTION.md` when working on citation logic.
- **Public Contracts:** Respect definitions in `docs/public-contracts.md`.
