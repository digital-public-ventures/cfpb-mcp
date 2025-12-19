# Test Strategy: CFPB Hybrid MCP + REST Server

This repo exposes the same CFPB Complaint Database capabilities through **two agent-facing interfaces**:

1. **MCP (Claude Desktop / Anthropic hosts)** via legacy SSE-style endpoints under `/mcp` (e.g. `/mcp/sse`).
2. **OpenAPI-described REST (ChatGPT Actions / OpenAI hosts)** via FastAPI endpoints and `/openapi.json`.

The goal of this strategy is to validate—via integration tests against a *running server*—that:

* MCP clients can connect and invoke all tools.
* OpenAI-style “Action selection via OpenAPI + operationId” can discover and call all REST endpoints.
* Feature parity holds (same functionality, equivalent parameter shapes, expected response types).

***

## Standards & Expectations (web research summary)

### MCP transport expectations

The MCP spec defines Streamable HTTP as the modern transport; it also documents backwards-compatibility for older HTTP+SSE approaches.

Key requirements from MCP Transports (protocol rev 2025-03-26):

* Streamable HTTP uses a single MCP endpoint for POST/GET; clients POST JSON-RPC messages and may receive either JSON or an SSE stream.
* Clients may open an SSE stream via GET if the server supports it.
* Session management may involve an `Mcp-Session-Id` header; resumability can use SSE `id` events and `Last-Event-ID`.
* Servers should validate `Origin` and should bind to localhost when running locally.

Source: <https://modelcontextprotocol.io/specification/2025-03-26/basic/transports>

### OpenAI GPT Actions expectations (OpenAPI)

OpenAI GPT Actions use OpenAPI schema to:

* decide which endpoint to call
* infer JSON inputs for that call

Important practical expectations from OpenAI docs:

* `operationId` and parameter descriptions strongly influence correct tool selection and argument filling.
* The schema should be testable outside ChatGPT (e.g., Postman) and then validated inside ChatGPT.
* Authentication can be None / API key / OAuth, with UI-managed config.

Sources:

* <https://platform.openai.com/docs/actions/introduction>
* <https://platform.openai.com/docs/actions/getting-started>
* <https://platform.openai.com/docs/actions/authentication>

***

## What we are testing (surfaces)

### REST surface (OpenAI/Actions)

* `GET /openapi.json` schema integrity
* `GET /search` (operationId: `searchComplaints`)
* `GET /trends` (operationId: `listTrends`)
* `GET /geo/states` (operationId: `getGeoStates`)
* `GET /suggest/{field}` (operationId: `suggestFilterValues`)
* `GET /complaint/{complaint_id}` (operationId: `getComplaintDocument`)

### MCP surface (Claude Desktop)

This repo currently mounts `FastMCP(...).sse_app()` at `/mcp`, which results in:

* `GET /mcp/sse` (SSE stream)
* `POST /mcp/messages` (client-to-server message ingress)

This matches the common “legacy SSE” pattern (stream endpoint + message endpoint) that many clients use.

***

## Test levels

### 1) Smoke tests (fast, deterministic)

Objective: catch obvious regressions quickly.

* Server starts.
* `GET /openapi.json` returns 200 and valid JSON.
* `GET /docs` returns 200.
* `GET /search?size=1` returns 200 and JSON.
* `GET /mcp/sse` returns 200 and `Content-Type: text/event-stream`.

### 2) Contract tests (interface correctness)

Objective: verify schema correctness and “agent expectations”.

**REST/OpenAPI contract checks**

* Validate OpenAPI document shape (`openapi` field present, `paths` present).
* Ensure each endpoint has a stable `operationId` (these are how Actions map tools).
* Ensure parameters appear in the expected location (`in: query` for filters, `in: path` for `complaint_id` and `field`).
* Ensure list-valued filters are represented as repeatable query params (FastAPI’s `Query(None)` yields this behavior).

**MCP contract checks**

* Validate that connecting via SSE works and the stream produces events.
* Validate that the server responds to the MCP initialization lifecycle and exposes tools.
  * Expected MCP JSON-RPC methods typically include: `initialize`, `tools/list`, `tools/call`, plus lifecycle notifications.
  * Tool names should match those declared in the server (e.g. `search_complaints`, `list_complaint_trends`, etc.).

Note: The exact wire details (event names, initialization payload) should follow the MCP SDK defaults for `FastMCP`. The tests should not “guess”; they should implement the real handshake using an MCP client library.

### 3) Parity tests (feature equivalence)

Objective: ensure both interfaces can do the same jobs.

For each capability, validate:

* MCP tool call works
* REST endpoint call works
* Returned JSON contains the expected top-level structures (e.g., `hits`, aggregations, etc.), and the results are *consistent enough* to be considered equivalent (exact values may change over time).

Suggested parity mapping:

| Capability | MCP tool | REST endpoint |
| --- | --- | --- |
| Search complaints | `search_complaints` | `GET /search` |
| Trends | `list_complaint_trends` | `GET /trends` |
| Geo aggregations | `get_state_aggregations` | `GET /geo/states` |
| Retrieve complaint by ID | `get_complaint_document` | `GET /complaint/{complaint_id}` |
| Suggest company / zip | `suggest_filter_values` | `GET /suggest/{field}` |

### 4) Negative tests (error behavior)

Objective: confirm agent-facing failures are meaningful.

REST:

* `GET /suggest/company?text=` returns 422 (FastAPI validation).
* `GET /suggest/badfield?text=x` returns 422.
* `GET /complaint/not-a-real-id` returns a 4xx or 5xx; assert the server surfaces upstream errors consistently.

MCP:

* Tool call with invalid arguments should yield JSON-RPC error response (not a server crash).
* Unknown method should yield JSON-RPC error.

***

## Integration test harness design

### Test framework

Recommend: `pytest` + `pytest-asyncio` (or `anyio`) + `httpx`.

Add test-only dependencies (via uv):

```bash
uv add --dev pytest pytest-asyncio anyio httpx jsonschema
```

For SSE parsing, either:

* implement a minimal SSE parser (read lines, split on `event:`/`data:`), or
* use an SSE helper library.

### Running server under test

Use a fixture that:

* starts the server in a subprocess with `uv run uvicorn server:app --host 127.0.0.1 --port 0`
* captures the chosen port (or pick a known test port, but random is safer)
* waits for readiness (`GET /openapi.json` until 200)
* tears down reliably

Important: MCP spec recommends localhost binding for local servers, which matches this approach.

### Avoiding flaky assertions

The CFPB upstream API is live and can change.

Guidelines:

* Prefer asserting response *shape* and invariants over exact values.
* Keep timeouts generous.
* Consider recording a small set of “known good” queries that are unlikely to break (e.g., generic `size=1`, or `suggest/company?text=bank`).

If you want true determinism, introduce a “record/replay” layer (e.g., VCR.py) later. Start with live integration tests first.

***

## MCP integration tests (Anthropic-agent simulation)

### Two ways to test MCP

1. **Black-box MCP client tests (recommended):**
   Use the official `mcp` Python client SDK to connect and perform the full handshake.

2. **Wire-level tests (backup):**
   Open `/mcp/sse`, parse events, and post JSON-RPC frames to `/mcp/messages`.

Because MCP evolves quickly and `FastMCP` may change wire details, prefer using the client SDK for correctness.

### Recommended MCP test cases

1. `test_mcp_can_connect_and_list_tools`

* Connect to `http://127.0.0.1:{port}/mcp/sse`.
* Perform initialize handshake.
* Call `tools/list`.
* Assert tool names include:
  * `search_complaints`
  * `list_complaint_trends`
  * `get_state_aggregations`
  * `get_complaint_document`
  * `suggest_filter_values`

1. `test_mcp_search_complaints_works`

* Call `search_complaints` with `size=1`.
* Assert JSON has `hits`.

1. `test_mcp_suggest_company_works`

* Call `suggest_filter_values(field="company", text="bank", size=5)`.
* Assert suggestions list is non-empty (or at least the expected keys exist).

1. `test_mcp_document_round_trip`

* First call `search_complaints(size=1)`.
* Extract complaint id from result.
* Call `get_complaint_document(complaint_id=...)`.
* Assert returned doc references that id.

***

## REST/OpenAPI integration tests (OpenAI-agent simulation)

### REST test cases

1. `test_openapi_has_operation_ids`

* Fetch `/openapi.json`.
* Assert presence of:
  * `/search` GET operationId `searchComplaints`
  * `/trends` GET operationId `listTrends`
  * `/geo/states` GET operationId `getGeoStates`
  * `/suggest/{field}` GET operationId `suggestFilterValues`
  * `/complaint/{complaint_id}` GET operationId `getComplaintDocument`

1. `test_search_accepts_repeatable_filters`

* Call `/search?company=Bank%20of%20America&company=Wells%20Fargo&size=1`.
* Assert 200 or a meaningful upstream error (some filters may yield 0 results but should not 500).

1. `test_suggest_field_enum`

* `/suggest/company?text=bank&size=3` returns 200
* `/suggest/zip_code?text=90&size=3` returns 200
* `/suggest/bad?text=x` returns 422

1. `test_complaint_document_via_id_from_search`

* Call `/search?size=1`.
* Extract an id.
* Call `/complaint/{id}`.

***

## Parity verification plan (MCP vs REST)

Create a shared “capability runner” interface in tests:

* `run_search(size=1, **filters)`
* `run_trends(...)`
* `run_geo(...)`
* `run_suggest(...)`
* `run_document(id)`

Then implement it twice:

* `McpRunner` uses the MCP tool calls.
* `RestRunner` calls the REST endpoints.

For each capability:

* Execute both runners.
* Validate results share expected shapes.
* Optionally validate they are “roughly consistent” (e.g., both return non-empty `hits` for the same query).

***

## Taking it further: SDK-based end-to-end agent harness

This section goes beyond integration tests and validates “real model + tool loop” behavior.

### Anthropic SDK + MCP tools loop (recommended)

Goal: prove an Anthropic model can only succeed by calling MCP tools.

Plan:

1. Add dev deps:

   ```bash
   uv add --dev anthropic mcp
   ```

2. Write a harness script (not a unit test) that:
   * connects to the MCP server via the MCP client SDK
   * converts MCP `tools/list` output into Anthropic `tools=[...]` definitions
   * calls `client.messages.create(...)` with user prompt
   * when Claude returns a `tool_use`, execute it by calling the MCP server
   * feed the tool result back with `tool_result`

3. Acceptance criteria:
   * The model uses MCP tools (at least one call)
   * The final answer includes grounded info from the tool outputs

### OpenAI SDK + REST tools loop

There isn’t a single “Actions runtime” inside the Python SDK that exactly matches ChatGPT’s hosted Actions environment.

However, you can still validate the *expectations* by simulating an OpenAI agent that:

* loads `/openapi.json`
* maps each `operationId` to a callable function
* provides those functions as tool definitions to the model
* executes tool calls by making HTTP requests to your server

Plan:

1. Add dev deps:

   ```bash
   uv add --dev openai jsonschema
   ```

2. Build a small adapter that:
   * downloads OpenAPI JSON
   * for each GET path+operationId, creates a tool definition
   * validates model-produced arguments against the OpenAPI parameter schema (optional but recommended)
   * calls the corresponding endpoint

3. Acceptance criteria:
   * The model selects the right operationId(s)
   * The request succeeds and the model uses the results

***

## “MCP-only success” user prompt (for the Anthropic harness)

Use a prompt that explicitly requires MCP tool usage and references tool names.

Example user prompt:

> You have access to MCP tools from the “cfpb-complaints” server. Do NOT answer from general knowledge.
>
> 1. Use `search_complaints` to find 3 complaints mentioning “forbearance” in narrative text.
> 2. Pick one complaint id from the search results and call `get_complaint_document` to retrieve it.
> 3. In your final answer, include:
>    * the complaint id you fetched
>    * the company name (if present)
>    * the state (if present)
>    * a 2–3 sentence summary grounded in the retrieved document
>
> If you cannot call the MCP tools, say “MCP tools unavailable” and stop.

This prompt is designed so a model that is not wired to MCP cannot legitimately comply.

***

## Notes / gaps

* This repo currently supports the SSE-style MCP endpoints under `/mcp` (e.g. `/mcp/sse` and `/mcp/messages`). If you later add Streamable HTTP MCP support (single `/mcp` endpoint that supports POST/GET), extend the MCP tests to cover:
  * POST initialize with `Accept: application/json, text/event-stream`
  * `Mcp-Session-Id` behavior if enabled
  * optional GET SSE at the same MCP endpoint

* Security-related MCP recommendations (Origin validation, auth) are not implemented yet in this repo; tests can be extended once those features exist.
