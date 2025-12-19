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

### Phase 1: The Wrapper (Live Connection)

*Goal: Get the server running and talking to the live CFPB API immediately.*

**Status in this repository:** Implemented. We already provide both interfaces:

* **REST/OpenAPI**: `GET /openapi.json` with primary endpoints like `/search`, `/trends`, `/geo/states`, `/suggest/...`, and `GET /complaint/{complaint_id}`.
* **MCP over SSE**: `GET /mcp/sse` (for Claude Desktop and other MCP-native clients).

1. **Setup:** Run a single FastAPI app alongside a `FastMCP` server, sharing a single `httpx.AsyncClient` for connection pooling.
2. **Direct Mapping:** Wrap the CFPB `ccdb5-api` endpoints via shared helper functions so REST routes and MCP tools reuse the same request/response shaping.
   * Implement core operations like `search_complaints` (MCP tool) and `GET /search` (REST) using the official API parameters (`state`, `product`, `company`, `date_received_min`, etc.).
   * **Important:** Use the [Field Reference](https://cfpb.github.io/api/ccdb/fields.html) to map messy agent inputs (e.g., "credit cards") to strict API values (e.g., `Credit card or prepaid card`).
3. **Output:** Return upstream JSON with minimal transformation, while defensively pruning invalid/empty query params to avoid avoidable 400s from the upstream CFPB API.

### Phase 2: The "Advocate" Engine (Vector & Hybrid Search)

*Goal: Enable semantic search for the "Ohio Student" use case. See (VISION.md)\[VISION.md]*

1. **Ingestion Pipeline:** Create a background job (Python script) that:
   * Downloads the bulk CSV (using the API or S3 export).
   * Chunks the `consumer_complaint_narrative` field.
   * Generates embeddings (via `sentence-transformers/all-MiniLM-L6-v2` or OpenAI `text-embedding-3-small`).
   * Stores vectors + metadata in Postgres `pgvector`.
2. **Hybrid Search Tool:**
   * *Input:* "Military family cheated by wells fargo mortgage."
   * *Logic:*
     1. Extract Filters (LLM or Regex): `company="Wells Fargo"`, `product="Mortgage"`.
     2. Vector Search: Cosine similarity on "Military family cheated".
     3. Post-Filter: Apply the SQL filters to the vector results.
   * *Output:* Top 5 specific narratives.

### Phase 3: The "Regulator" Dashboard (Trends & Artifacts)

*Goal: Analytical tools and word associations.*

1. **Trend Aggregation:**
   * Use Postgres Materialized Views to calculate monthly volumes per product/company.
   * Refresh these views daily.
2. **Word Association (NLU):**
   * Implement `get_word_associations(term)`.
   * *Implementation:* Use Postgres TSVECTOR or a simple Python `Counter` on the filtered narratives to find top co-occurring adjectives/nouns (e.g., "Venmo" + "frozen", "locked", "scam").
3. **Visual Artifacts (Graphing):**
   * Instead of returning just numbers, use `matplotlib` or `plotly` to generate a plot image (Base64 encoded).
   * Return this as an **MCP Image Resource** so the agent can display the chart directly to the user.

***

## 5. Deployment Instructions (For the Coding Agent)

**1. Environment Setup**

```bash
uv add mcp[cli] httpx pgvector redis pandas sentence-transformers
```

**2. Database Schema (Postgres)**
Create a table `complaints` with:

* `complaint_id` (Primary Key)
* `narrative_text` (Text)
* `embedding` (vector(384))
* `metadata` (JSONB - stores state, product, company, dates)
* *Index:* HNSW index on `embedding` for fast cosine similarity.

**3. Server Entry Point (`server.py`)**
Use the `FastMCP` pattern for cleaner code:

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

## 6. Speculation: The "Harness" as an Artifact Generator

*You asked for wilder ideas. Here is the "Galaxy Brain" architecture.*

The **CFPB CCDB5 UI** (the frontend harness) is a masterpiece of accessible government design. It already knows how to render accessible, beautiful charts and handle URL-state mapping.

Instead of just replicating the *logic* of the harness, we can **weaponize the harness itself** inside the MCP server.

**Concept: "Headless Harness Rendering"**

1. **The URL Hack:** The CCDB5 UI is state-driven by URL parameters.
   * *Example:* `consumerfinance.gov/data-research/consumer-complaints/search/?date_received_max=2025-12-18&searchTerm=subprime`
2. **The MCP Tool:** `generate_official_chart_url(filters: dict)`
   * The MCP server constructs the exact deep-link to the official CFPB visualization tool.
   * The Agent presents this URL to the user: "I've configured an interactive dashboard for you to explore this data \[Click Here]."
3. **The Screenshot Service (Wild):**
   * The MCP server runs a lightweight headless browser (Playwright).
   * When the user asks for a "trend line," the server constructs the CCDB5 URL, loads it in the headless browser, waits for the D3.js chart to render, takes a screenshot of *just the chart div*, and returns it as an image artifact.
   * **Benefit:** You get official, recognizable, verified CFPB branding on the charts without writing a single line of graphing code.

**Why this works for the "Regulator" use case:**
If we are standing in for the regulator, using their exact visual language adds authority. When an Advocate presents a case to a Senator, showing a chart that looks exactly like the official government dashboard is more powerful than a generic Matplotlib graph.
