This report outlines the implementation guidelines for building a robust Model Context Protocol (MCP) server for the Consumer Financial Protection Bureau (CFPB) database.

**Date:** December 18, 2025
**To:** Lead Coding Agent / Engineering Team
**From:** Gemini (AI Architect)
**Subject:** CFPB MCP Server Architecture & Implementation Specification

***

## 1. Executive Summary: The State of MCP in Late 2025

As of today, the Model Context Protocol (MCP) has stabilized into the standard "USB-C" for AI tool connectivity.

* **Claude (Desktop & Web):** Native support. Works out of the box via `stdio` (Desktop) or SSE (Web).
* **ChatGPT (OpenAI):** Requires an **Adapter/Bridge**. OpenAI’s native "Actions" and "Realtime API" are distinct from MCP. We will implement a lightweight "MCP-to-OpenAI" bridge that exposes our MCP tools as OpenAI Function definitions.
* **Gemini:** Similar to OpenAI, requires a translation layer to map MCP tools to Gemini Function Calling.

**Core Philosophy:** We will build a **Python-based MCP Server** that prioritizes *semantic intelligence* over simple API wrapping. The raw CFPB API is rigid; our server will make it fluid for natural language agents.

***

## 2. Functional Requirements & Use Case Mapping

We have translated the stakeholder's narrative goals from [VISION.md](VISION.md) into specific technical requirements and MCP Tool definitions.

Before diving into the goals below, note that this repository is **already past “Phase 1: The Wrapper”** in several important ways. We currently have a working, end-to-end service that exposes the CFPB complaint data to both MCP-native clients (Claude) and OpenAPI-native clients (ChatGPT Actions), with a test suite and a few explicit contract choices that are intended to keep future work from regressing integration behavior.

What’s already implemented (high level):

* A single FastAPI server that exposes both **REST/OpenAPI** endpoints and **MCP tools over SSE** (mounted at `/mcp/sse`).
* Shared, transport-agnostic helper logic (REST routes and MCP tools reuse the same underlying request/response shaping).
* Defensive upstream parameter handling to avoid CFPB API errors (e.g., we prune `None` / empty values rather than forwarding them).
* A deterministic pytest suite for REST + MCP flows, plus **opt-in** provider E2E tests (treated as a long-term compatibility contract).
* Lightweight harness scripts to exercise both integration modes (useful for manual smoke checks).

Context-setting choices (why these goals are sequenced the way they are):

* **Dual-protocol is a core constraint:** we treat OpenAPI (`/openapi.json`) and MCP SSE (`/mcp/sse`) as first-class public interfaces, not “nice-to-have adapters.”
* **Stability over cleverness:** the repo explicitly treats `tests/e2e/**` as immutable contracts; if we need breaking changes, we add a new versioned suite rather than modifying the existing one.
* **Semantics come later by design:** semantic/vector search, epoch logic, and anomaly detection can be layered on top of the already-working wrapper without changing client integration patterns.

### Goal 1: Arming the Advocates (Semantic & Narrative Search)

* **Objective:** Find specific "constituent stories" matching complex fact patterns (e.g., "Student in Ohio screwed by subprime auto loan").
* **Problem:** The CFPB API supports filtering by State/Product, but *not* by narrative content (semantic search).
* **MCP Solution:** Hybrid Search (Keyword Filters + Vector Similarity).
  * **Tool:** `find_similar_complaints(query: str, state_code: str, product: str)`
  * **Tool:** `search_narratives_by_semantic_match(description: str, limit: int)`
  * **Resource:** `complaint://{id}/narrative` (Direct text access for context window).

### Goal 2: Telling the Story of the CFPB (Longitudinal Analysis)

* **Objective:** Analyze complaint volume and sentiment across the "Four Epochs" (Warren Era, Growth, Trump Era, Modern Era).
* **MCP Solution:** Pre-calculated aggregations and epoch-aware filtering.
  * **Tool:** `get_complaint_volume_by_epoch(epoch_name: str | date_range)`
  * **Tool:** `compare_trends(product: str, year_start: int, year_end: int)`
  * **Sub-requirement:** The server must map natural language epochs (e.g., "The Trump Years") to specific date ranges (`2017-01-20` to `2021-01-20`) internally.

### Goal 3: Standing in as the Regulator (Real-time Signal Detection)

* **Objective:** Identify "smoke signals"—sudden spikes in complaints (e.g., Rush Card outage equivalent) or new abuse vectors (BNPL, crypto).
* **MCP Solution:** Statistical anomaly detection and trend velocity tools.
  * **Tool:** `detect_anomaly_by_company(company_name: str, lookback_days: int)`
  * **Tool:** `get_emerging_issues(product_category: str)` (scans for keywords like "outage", "locked out", "fraud" with high velocity).
  * **Tool:** `analyze_word_associations(topic: str)` (e.g., what words co-occur with "Venmo" vs "Bank of America").

***

## 3. Technical Architecture

### Stack

* **Language:** Python 3.12+
* **Core Library:** `mcp` (Official Python SDK)
* **Server Transport:**
  * **Stdio:** For local Claude Desktop / Cursor usage.
  * **SSE (Server-Sent Events):** For remote agents and web clients.
* **Database:** PostgreSQL 17 with `pgvector` extension.
* **Caching:** Redis (for high-volume aggregations like "total complaints per year").

### The "Bridge" Pattern (Crucial for ChatGPT)

Since ChatGPT does not natively speak MCP yet, we will deploy a **Middleware Bridge**:

1. **Ingest:** The Bridge reads our MCP `list_tools` manifest.
2. **Translate:** Converts MCP JSON schema $\rightarrow$ OpenAI/Gemini Function Schema.
3. **Route:** Receives OpenAI function calls $\rightarrow$ executes MCP tool $\rightarrow$ returns result.

***

## 4. Implementation Guidelines (Phased)

### ✅ Phase 1: The Wrapper (Live Connection) ✅

*Goal: Get the server running and talking to the live CFPB API immediately.*

**Status in this repository:** Implemented. We already provide both interfaces:

* **REST/OpenAPI**: `GET /openapi.json` with primary endpoints like `/search`, `/trends`, `/geo/states`, `/suggest/...`, and `GET /complaint/{complaint_id}`.
* **MCP over SSE**: `GET /mcp/sse` (for Claude Desktop and other MCP-native clients).

1. **Setup:** Run a single FastAPI app alongside an MCP server implementation (this repo uses `FastMCP` today), sharing a single `httpx.AsyncClient` for connection pooling.
2. **Direct Mapping:** Wrap the CFPB `ccdb5-api` endpoints via shared helper functions so REST routes and MCP tools reuse the same request/response shaping.
   * Implement core operations like `search_complaints` (MCP tool) and `GET /search` (REST) using the official API parameters (`state`, `product`, `company`, `date_received_min`, etc.).
   * **Important:** Use the [Field Reference](https://cfpb.github.io/api/ccdb/fields.html) to map messy agent inputs (e.g., "credit cards") to strict API values (e.g., `Credit card or prepaid card`).
3. **Output:** Return upstream JSON with minimal transformation, while defensively pruning invalid/empty query params to avoid avoidable 400s from the upstream CFPB API.

### ✅ Phase 2: Docker Compose Stack (Server + pgvector Postgres) ✅

*Goal: Stand up a reproducible local stack (app + database) so the next phases can iterate quickly and safely.*

1. **Docker Compose stack:** Add a `docker-compose.yml` that runs:
   * **Server container**: a lightweight (but not ultra-minimal) Linux base image, running the FastAPI app.
     * Expose the server as **`localhost:8002`** (host port `8002` mapped to container port `8000`).
   * **Postgres + pgvector container**: built from the **latest pgvector base** (rather than “vanilla” Postgres).
     * Persist data via a named volume.
     * Include an init script for extensions / schema setup (added in Phase 5).
2. **Container networking:** Configure the server to reach Postgres via the compose service name (e.g., `postgres:5432`).
3. **Dev ergonomics:** Provide a single `docker compose up --build` path that works on Apple Silicon (arm64).

*Note:* Until Phase 5, Postgres is present primarily so we can wire the plumbing early (connection management, migrations/init scripts, and local reproducibility), even while the actual query behavior continues to proxy the public CFPB API.

*Note:* In the Docker Compose stack, Postgres is mapped to host port `5433` (instead of `5432`) to avoid clobbering a developer’s locally-installed Postgres.

### Phase 3: Proxy-First Productization (Public CFPB API)

*Goal: Go as far as possible by proxying the public CFPB API before we touch local ingestion/embeddings.*

1. **Proxy-first feature completion:** Ensure the server can satisfy the majority of advocate/regulator questions purely via the live CFPB endpoints:
   * Search, complaint document fetch, trends, geo aggregations, and suggestion endpoints.
   * Normalize/validate parameters and aggressively prune empty/invalid values to avoid upstream 400s.
2. **Shared logic contract:** Keep one set of helper functions that are reused by both transports (REST and MCP), so later phases can swap data sources (remote API → local Postgres/vector search) without changing the public interfaces.
3. **Output discipline:** Prefer returning upstream JSON (minimal transformation) and add formatting/aggregation only when it clearly improves agent usability.

### ✅ Phase 4: The "Regulator" Layer (Analytics on Top of Proxy) ✅

*Goal: Add lightweight analytical tools that do not require local ingestion yet.*

1. **Date-range trend queries (proxy-based):** Rely on the calling agent to supply explicit date ranges, and ensure our endpoints/tools make that easy via `date_received_min` / `date_received_max` (ISO date strings). For example, “2017–2020” can be expressed as `date_received_min=2017-01-01` and `date_received_max=2020-12-31`.
2. **Signal helpers (proxy-based):** Add anomaly-leaning helpers computed from upstream `trends` results (velocity/spike heuristics) before we introduce local materialized views.
   * Implement as small, auditable helpers (REST + MCP) that return both the scores and the underlying buckets used.
   * Start with month-level signals (the most reliable upstream interval observed) and **drop the current-month partial bucket** before computing “latest vs previous/baseline” to avoid false drops.
   * Support both direct group-based signals (e.g., `product`, `issue`) via `sub_lens=...` and pipeline-based signals where upstream doesn’t group cleanly (e.g., **company spikes** via `search(size=0)` → top company buckets → `trends` per company).

### ✅ Phase 4.5: The "Harness" as an Artifact Generator ✅

The **CFPB CCDB5 UI** (the frontend harness) is a masterpiece of accessible government design. It already knows how to render accessible, beautiful charts and handle URL-state mapping.

Instead of just replicating the *logic* of the harness, we can **weaponize the harness itself** inside the MCP server.

**Concept: "Headless Harness Rendering"**

1. **The URL Hack:** The CCDB5 UI is state-driven by URL parameters.
   * *Example:* `consumerfinance.gov/data-research/consumer-complaints/search/?date_received_max=2025-12-18&searchTerm=subprime`
2. **The MCP Tool:** `generate_official_chart_url(filters: dict)`
   * The MCP server constructs the exact deep-link to the official CFPB visualization tool. This can be derived from analyzing (/docs/CFPB\_URL\_SCHEME.md)\[/docs/CFPB\_URL\_SCHEME.md]
   * The Agent presents this URL to the user: "I've configured an interactive dashboard for you to explore this data \[Click Here]."
3. **The Screenshot Service:**
   * The MCP server runs a lightweight headless browser (Playwright).
   * When the user asks for a "trend line," the server constructs the CCDB5 URL, loads it in the headless browser, waits for the D3.js chart to render, takes a screenshot of *just the chart div*, and returns it as an image artifact.
   * **Benefit:** You get official, recognizable, verified CFPB branding on the charts without writing a single line of graphing code.

**Why this works for the "Regulator" use case:**
If we are standing in for the regulator, using their exact visual language adds authority. When an Advocate presents a case to a Senator, showing a chart that looks exactly like the official government dashboard is more powerful than a generic Matplotlib graph.

### ✅ Phase 4.6: Citation URLs for Verification & Transparency ✅

**Goal:** Every MCP server response should include clickable citation URLs that link directly to the official CFPB UI, allowing users to verify data and explore further.

**Concept: "Show Your Work"**

When an AI agent asks our MCP server for complaint data, we don't just return raw JSON—we also provide deep-links to the exact view on the official CFPB website that matches the query. This enables:

1. **Verification**: Users can click through to verify the AI's claims against the source of truth
2. **Exploration**: Users can interactively explore the data beyond what the AI surfaced
3. **Authority**: Links to `.gov` domains carry inherent credibility
4. **Audit Trail**: Each response is traceable back to the official government database

**Implementation Strategy:**

1. **URL Builder Enhancement**: Extend the existing `build_cfpb_ui_url()` function to support all query parameters (documented in `/docs/CFPB_UI_URL_CONSTRUCTION.md`)

2. **Response Wrapper Pattern**: Add a `citations` array to all MCP tool responses:
   ```json
   {
     "data": {...},
     "citations": [
       {
         "type": "search_results",
         "url": "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=List&searchText=foreclosure&product=Mortgage&date_received_min=2020-01-01",
         "description": "View these results on CFPB.gov"
       },
       {
         "type": "trends_chart",
         "url": "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=Trends&lens=Product&product=Mortgage&date_received_min=2020-01-01&chartType=line&dateInterval=Month",
         "description": "Interactive trends chart on CFPB.gov"
       }
     ]
   }
   ```

3. **Smart Tab Selection**:
   * Search queries → `tab=List`
   * Trend queries → `tab=Trends`
   * Geographic queries → `tab=Map`
   * Complaint document fetches → Direct link to complaint (if available publicly)

4. **Parameter Mapping**: Map internal query parameters to UI parameters using the comprehensive reference in `/docs/CFPB_UI_URL_CONSTRUCTION.md`:
   * Handle multi-value parameters (products, states, issues)
   * Proper URL encoding (spaces as `%20`, commas as `%2C`)
   * Include all active filters to ensure URL matches the query exactly

5. **Citation Types**:
   * `search_results` - List view of matching complaints
   * `trends_chart` - Trends visualization
   * `geographic_map` - Map view by state
   * `company_profile` - Company-specific view
   * `complaint_detail` - Individual complaint (when complaint\_id is known)

**Example Scenarios:**

**Scenario 1: Search Query**

```
User: "Find mortgage complaints in California from 2023"
MCP Response:
{
  "data": {"hits": [...]},
  "citations": [{
    "type": "search_results",
    "url": "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=List&product=Mortgage&state=CA&date_received_min=2023-01-01&date_received_max=2023-12-31",
    "description": "View all 1,234 matching complaint(s) on CFPB.gov"
  }]
}
```

**Scenario 2: Trend Analysis**

```
User: "Show me mortgage complaint trends over the past 2 years"
MCP Response:
{
  "data": {"aggregations": {...}},
  "citations": [{
    "type": "trends_chart",
    "url": "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=Trends&lens=Product&product=Mortgage&date_received_min=2022-12-01&chartType=line&dateInterval=Month",
    "description": "Interactive mortgage complaint trends on CFPB.gov"
  }]
}
```

**Scenario 3: Company Analysis**

```
User: "Analyze Wells Fargo complaints"
MCP Response:
{
  "data": {...},
  "citations": [
    {
      "type": "trends_chart",
      "url": "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=Trends&lens=Company&company=WELLS%20FARGO%20%26%20COMPANY&dateInterval=Month",
      "description": "Wells Fargo complaint trends on CFPB.gov"
    },
    {
      "type": "search_results",
      "url": "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=List&company=WELLS%20FARGO%20%26%20COMPANY",
      "description": "Browse matching complaints on CFPB.gov"
    }
  ]
}
```

**Benefits for Different User Personas:**

* **Advocates**: Can send constituents authoritative .gov links to explore their issue
* **Regulators**: Can cite official sources in reports and presentations
* **Researchers**: Can reproduce queries and verify AI-generated insights
* **General Users**: Can gain confidence that the AI isn't hallucinating data

**Technical Notes:**

* URLs are constructed client-side (no server-side redirect needed)
* All URLs are read-only (no state modification)
* URLs work without authentication (public data)
* URLs are stable and shareable
* See `/docs/CFPB_UI_URL_CONSTRUCTION.md` for complete parameter reference

**Implementation Summary:**

✅ Extended `build_cfpb_ui_url()` to support all UI display parameters (tab, lens, chartType, dateInterval, subLens)\
✅ Created `generate_citations()` helper with smart tab selection based on context\
✅ Wrapped MCP tool responses: `search_complaints`, `list_complaint_trends`, `get_state_aggregations`\
✅ Added 16 comprehensive tests in `tests/test_citations.py` validating URL construction and citation generation\
✅ All tests passing (43 passed, 3 skipped E2E tests)\
✅ Response format: `{"data": <original_payload>, "citations": [...]}`

### Phase 5: Claude Custom Connector (Remote, OAuth)

**Goal:** Treat Claude Custom Connectors as the primary integration path for production (remote HTTPS + OAuth). This replaces the earlier `.mcpb` packaging plan.

#### (Deprecated) Phase 5.1: Claude Desktop Extension (.mcpb)

We are no longer pursuing `.mcpb` packaging. Any `.mcpb` plans and related implementation artifacts are slated for removal in Phase 5.5.

#### ✅ Phase 5.2: Claude Custom Connector - Direct Remote Access (Cloudflare Tunnel) ✅

**Goal:** Allow Claude (Desktop, Web, Mobile) to connect directly to the remote MCP server over HTTPS.

**Status in this repository:** Implemented (Cloudflare Tunnel + remote endpoint operational).

**Critical invariants (do not break):**

* Remote MCP endpoint remains stable and reachable over HTTPS.
* Tool names/schemas remain stable.
* Existing REST/OpenAPI surface remains available.

#### Phase 5.3: FastMCP Migration + Dual Transport (Pre-OAuth)

**Goal:** Standardize on the `fastmcp` library for MCP serving, so we can support both Streamable HTTP and legacy SSE from the same framework before adding OAuth.

**Why this comes before OAuth:** FastMCP’s auth patterns (Token Verification / Remote OAuth / OAuth Proxy) are designed to sit “above” the transport layer; migrating first avoids implementing OAuth twice.

**Deliverables:**

1. **Migrate MCP server implementation to `fastmcp`:**
   * Replace usage of the MCP SDK server with FastMCP (`fastmcp.FastMCP`) while preserving tool names, schemas, and outputs.
   * Keep the existing FastAPI REST surface unchanged.

2. **Expose dual transports simultaneously:**
   * Streamable HTTP MCP endpoint: `POST /mcp` (recommended remote standard)
   * Legacy SSE MCP endpoint: `GET /mcp/sse` (compat / transition)

3. **Compatibility + invariants:**
   * Tool list and tool call behavior remains stable.
   * Responses remain deterministic and match existing tests.
   * Keep Cloudflare/host-header constraints in mind for external access.

4. **Testing + infra:**
   * Add `docker-compose.test.yml` so E2E runs do not collide with the non-test stack (ports, volumes, container names).
   * Do not edit `tests/e2e/**`; if transport/OAuth behavior changes require new contracts, add a new suite.

**Files to touch (expected / scoped):**

* `server.py` (swap MCP implementation to `fastmcp`, mount `/mcp` + `/mcp/sse`)
* `pyproject.toml` and `uv.lock` (add `fastmcp`, remove/adjust old MCP SDK dependency if no longer needed)
* `docker/server/Dockerfile` (ensure container build installs the updated dependencies)
* `docker-compose.yml` (only if we need to expose/add paths or env vars for the new endpoints)
* `tests/` (update or add unit/integration tests for `/mcp` and `/mcp/sse`; do not edit `tests/e2e/**`)
* `scripts/` (update any harnesses that assume only `/mcp/sse`)

**Acceptance criteria:**

* Both endpoints work concurrently (`/mcp` and `/mcp/sse`).
* Existing non-auth flows still pass current unit/integration tests.
* E2E still passes (or remains skipped) without modifying `tests/e2e/**`.

#### Phase 5.4: OAuth for Claude Custom Connector (FastMCP-Recommended)

**Goal:** Implement OAuth compatible with Claude Custom Connectors (OAuth client id/secret; no API keys), using FastMCP’s recommended auth patterns.

**Auth-spec reference:** See `/planning/mcp-oauth-best-practices.md`.

**Key FastMCP guidance to follow:**

* Prefer an external identity provider over a “full OAuth server” (FastMCP documents full OAuth as an advanced pattern to avoid unless required).
* Use **OAuth Proxy** for providers that do not support Dynamic Client Registration (DCR) (e.g., Google, GitHub, Azure/Entra).
* Ensure OAuth discovery routes are available at root-level well-known paths per RFC 8414 / RFC 9728.
* Maintain the invariant: `base_url + mcp_path = externally accessible MCP URL`.

**Implementation plan (high-level):**

1. Configure the chosen auth approach (Token validation / Remote OAuth / OAuth Proxy).
2. Publish `/.well-known/oauth-protected-resource` and related discovery endpoints.
3. Implement selective auth semantics (allow initialize/initialized; require auth for tools/list + tools/call).
4. Add OAuth-focused tests without modifying `tests/e2e/**`.

**Acceptance criteria:**

* Claude Custom Connector can authenticate via OAuth and successfully list/call tools.
* Discovery endpoints are reachable and consistent with the public MCP URL.
* OAuth applies identically to both `/mcp` and `/mcp/sse`.

#### Phase 5.5: Cleanup After OAuth-Only (Remove mcpb + API Keys)

**Goal:** Remove legacy and temporary scaffolding now that OAuth is the only supported production auth path.

**Cleanup checklist:**

* Delete `.mcpb`-related implementation artifacts and docs.
  * Remove the `deployment/` directory if it only exists to support the `.mcpb` packaging approach.
* Remove API-key auth and all related configuration/docs/tests:
  * Delete API-key middleware and rate-limit knobs that are only needed for API keys.
  * Remove `X-API-Key` references from docs.
  * Remove API-key generation instructions.
* Replace or supersede any API-key-oriented integration tests with OAuth-oriented tests.
  * Do not edit `tests/e2e/**`; add a new OAuth E2E suite instead (e.g., `tests/e2e_oauth/`) if the contract changes.

### Phase 6: Local Dataset + Vector Embeddings (MiniLM on Apple Silicon)

*Goal: Enable semantic narrative search (the “Ohio Student” use case) using local data and pgvector/halfvec.*

0. **Dataset availability:** The CFPB dataset slice is available locally at `/data/complaints.json` as a single ~2GB JSON file containing roughly the last 3 years.
   * Assumption: it is a flat array of standardized complaint objects.
1. **Safety-first inspection:** Before any ingestion, add a tiny script that can preview the “head” of `complaints.json` without loading the entire file into memory.
   * It should stream/parse incrementally and print the first $N$ objects (or selected fields like id/company/product/narrative length).
2. **Postgres schema (half-precision vectors):** Use `halfvec(384)` to reduce RAM/storage and enable HNSW search.

```sql
CREATE EXTENSION vector;

-- For NLU-style keyword search and term co-occurrence.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE complaints (
   -- Use the CFPB complaint id as the primary key.
   complaint_id bigint PRIMARY KEY,

   -- Store the narrative separately (often large, and may be missing).
   narrative text,

   -- Store the full complaint payload (everything except the narrative), including complaint_id.
   metadata jsonb NOT NULL,

   -- Use halfvec(384) instead of vector(384) to save ~50% RAM.
   embedding halfvec(384),

   -- Generated text index for NLU/search (Postgres full-text search).
   narrative_tsv tsvector GENERATED ALWAYS AS (
      to_tsvector('english', coalesce(narrative, ''))
   ) STORED
);

-- Create the HNSW index for fast search
CREATE INDEX ON complaints USING hnsw (embedding halfvec_l2_ops);

-- Full-text search index for narrative keyword queries.
CREATE INDEX ON complaints USING gin (narrative_tsv);
```

3. **Embedding model choice:** Use `sentence-transformers/all-MiniLM-L6-v2`.
   * Apple Silicon strategy (M4 MacBook): run embeddings on-device using PyTorch MPS acceleration when available.
   * Use batching sized to avoid memory pressure (prefer smaller batch sizes + streaming ingestion over “load all then embed”).
4. **Ingestion approach:** Stream the JSON array and upsert into Postgres.
   * Set `complaint_id` from the dataset.
   * Put the full complaint object into `metadata` **minus** the narrative field.
   * Store `narrative` separately.
   * Compute a 384-dim embedding from `narrative` when present.
   * Store embeddings in half precision (convert `float32` → `float16` before insert) to match `halfvec(384)`.
5. **Hybrid search:** Combine metadata filters (company/product/state/date) with vector similarity.

***

## 5. Deployment Instructions (For the Coding Agent)

**1. Environment Setup**

```bash
uv add mcp[cli] httpx pgvector redis pandas sentence-transformers
```

**2. Database Schema (Postgres)**
Use `halfvec(384)` for embeddings to reduce memory/storage and support HNSW search:

```sql
CREATE EXTENSION vector;

CREATE TABLE complaints (
   complaint_id bigint PRIMARY KEY,
   narrative text,
   metadata jsonb NOT NULL,
   embedding halfvec(384),
   narrative_tsv tsvector GENERATED ALWAYS AS (
       to_tsvector('english', coalesce(narrative, ''))
   ) STORED
);

CREATE INDEX ON complaints USING hnsw (embedding halfvec_l2_ops);
CREATE INDEX ON complaints USING gin (narrative_tsv);
```

**3. Server Entry Point (`server.py`)**
In Phase 6 we standardize MCP wiring on the `FastMCP` pattern (after the proxy + data layers are stable):

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CFPB-Intel")

@mcp.tool()
async def search_complaints(query: str, state: str = None) -> str:
    """
    Search for complaints using semantic meaning. 
    Useful for finding stories like 'veteran with foreclosure issues'.
    """
    # 1. Embed query
    # 2. Query pgvector with optional metadata filters
    # 3. Return formatted narratives
    pass

if __name__ == "__main__":
    mcp.run()
```

***
