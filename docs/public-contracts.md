# Public Contracts

This project intentionally supports *third-party* integrations (agents, tool runners, and automations) over HTTP (OpenAPI) and MCP.

To make major internal refactors safe for integrators, we treat the following endpoints as stable public contracts:

* `GET /openapi.json` — OpenAPI discovery document for the REST interface.
* `GET /complaint/{complaint_id}` — Retrieve a single complaint document by id.
* `GET /mcp/sse` — MCP Server-Sent Events (SSE) endpoint.

## Compatibility notes

* These paths are considered **stable** across major refactors.
* Behavior may evolve, but breaking changes to these endpoints should be avoided; if unavoidable, they should be versioned (e.g. add new endpoints rather than changing these paths).
* Internal implementation details (framework wiring, helper functions, tool schemas, etc.) are not part of the public contract.
