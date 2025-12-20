# FastMCP vs REST/OpenAPI Parity Audit

Date: 2025-01-25

## Scope

Determine whether the legacy REST/OpenAPI endpoints can be removed in favor of
FastMCP Streamable HTTP (`POST /mcp`) without losing functionality needed by
OpenAI/Anthropic integrations.

## Sources Reviewed

- `server.py` (FastMCP tools + REST routes)
- `tests/test_rest_endpoints.py` (REST smoke coverage)

## Endpoint-to-Tool Mapping

**REST** `GET /search`  
**MCP tool** `search_complaints`  
**Parity** Yes (same upstream search; MCP response wraps `data` + `citations`).

**REST** `GET /trends`  
**MCP tool** `list_complaint_trends`  
**Parity** Yes (same upstream trends; MCP response wraps `data` + `citations`).

**REST** `GET /geo/states`  
**MCP tool** `get_state_aggregations`  
**Parity** Yes (same upstream geo; MCP response wraps `data` + `citations`).

**REST** `GET /suggest/{field}`  
**MCP tool** `suggest_filter_values`  
**Parity** Yes (same upstream suggestion behavior).

**REST** `GET /complaint/{complaint_id}`  
**MCP tool** `get_complaint_document`  
**Parity** Yes (same upstream document fetch).

**REST** `GET /signals/overall`  
**MCP tool** `get_overall_trend_signals`  
**Parity** Yes (same logic; REST enforces required date range, MCP does not).

**REST** `GET /signals/group`  
**MCP tool** `rank_group_spikes`  
**Parity** Yes (same logic; REST enforces required date range, MCP does not).

**REST** `GET /signals/company`  
**MCP tool** `rank_company_spikes`  
**Parity** Yes (same logic; REST enforces required date range, MCP does not).

**REST** `GET /cfpb-ui/url`  
**MCP tool** `generate_cfpb_dashboard_url`  
**Parity** Yes (same URL builder; REST returns `{ "url": ... }`, MCP returns a string).

**REST** `GET /cfpb-ui/screenshot`  
**MCP tool** *none* (tool commented out)  
**Parity** **No**. REST route exists but intentionally returns 503. MCP tool is disabled.

**REST** `GET /openapi.json` / `GET /docs`  
**MCP tool** *n/a*  
**Parity** Not applicable to MCP. These are REST/OpenAPI scaffolding only.

## Behavioral Differences

- **Response shapes**: MCP tools for search/trends/geo wrap data + citations, while REST returns only raw data.
- **Required inputs**: REST signals endpoints require date ranges via `Query(...)`. MCP tools accept optional dates.
- **Screenshot**: Neither transport provides an active screenshot capability right now, but REST still exposes a 503 stub while MCP has no tool.

## Coverage Assessment

Everything in `tests/test_rest_endpoints.py` is functionally available via FastMCP **except** the OpenAPI scaffolding and the disabled screenshot endpoint:

- **Covered by MCP**: search, trends, geo, suggest, complaint doc, signals (overall/group/company), URL generation.
- **Not covered by MCP**: OpenAPI endpoints (`/openapi.json`, `/docs`), screenshot (tool disabled).

## Recommendation

If the goal is to retire REST/OpenAPI entirely:

1. Decide whether the **screenshot** feature should remain permanently disabled.  
   - If yes, remove it from REST *and* MCP plans/tests.  
   - If no, re-enable the MCP tool first, then retire REST.

2. Confirm any **client dependencies** on `/openapi.json` or `/docs` are gone.  
   - These are unrelated to MCP; removing REST removes them.

3. If dropping REST tests, replace them with **MCP-level parity tests** that exercise:
   - `search_complaints`, `list_complaint_trends`, `get_state_aggregations`
   - `suggest_filter_values`, `get_complaint_document`
   - `get_overall_trend_signals`, `rank_group_spikes`, `rank_company_spikes`
   - `generate_cfpb_dashboard_url`

## Conclusion

FastMCP currently covers the core functional API surface. The only true gap is
the disabled screenshot capability, plus OpenAPI scaffolding. Dropping REST is
safe **only if** you accept losing `/openapi.json` and the stub screenshot route,
or you migrate those responsibilities into MCP first.
