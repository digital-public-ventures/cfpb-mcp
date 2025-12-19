# IDEA

Here is the refactored "Hybrid" server. It runs a single FastAPI application that exposes **both**:

1. **MCP Protocol** (at `/mcp` for Claude Desktop)
2. **REST API** (at `/search`, `/trends`, etc. for ChatGPT Actions)

This allows you to run one codebase that serves both platforms simultaneously.

### `server.py`

```python
import requests
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, Query, Path
from mcp.server.fastapi import McpServer
import uvicorn

# 1. Initialize FastAPI and MCP
app = FastAPI(
    title="CFPB Complaint API",
    description="A hybrid MCP/REST server for accessing the Consumer Complaint Database.",
    version="1.0.0"
)
server = McpServer("cfpb-complaints")

BASE_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"

# 2. Shared Logic (Decoupled from Transport)
def build_params(
    search_term: Optional[str],
    field: Optional[str],
    company: Optional[List[str]],
    company_public_response: Optional[List[str]],
    company_response: Optional[List[str]],
    consumer_consent_provided: Optional[List[str]],
    consumer_disputed: Optional[List[str]],
    date_received_min: Optional[str],
    date_received_max: Optional[str],
    company_received_min: Optional[str],
    company_received_max: Optional[str],
    has_narrative: Optional[List[str]],
    issue: Optional[List[str]],
    product: Optional[List[str]],
    state: Optional[List[str]],
    submitted_via: Optional[List[str]],
    tags: Optional[List[str]],
    timely: Optional[List[str]],
    zip_code: Optional[List[str]]
) -> Dict[str, Any]:
    params = {
        "search_term": search_term,
        "field": field,
        "company": company,
        "company_public_response": company_public_response,
        "company_response": company_response,
        "consumer_consent_provided": consumer_consent_provided,
        "consumer_disputed": consumer_disputed,
        "date_received_min": date_received_min,
        "date_received_max": date_received_max,
        "company_received_min": company_received_min,
        "company_received_max": company_received_max,
        "has_narrative": has_narrative,
        "issue": issue,
        "product": product,
        "state": state,
        "submitted_via": submitted_via,
        "tags": tags,
        "timely": timely,
        "zip_code": zip_code,
    }
    return {k: v for k, v in params.items() if v is not None}

async def search_logic(
    size: int, from_index: int, sort: str, search_after: Optional[str], 
    no_highlight: bool, **filters
) -> Any:
    params = build_params(**filters)
    params.update({
        "size": size,
        "frm": from_index,
        "sort": sort,
        "search_after": search_after,
        "no_highlight": no_highlight,
        "no_aggs": False
    })
    response = requests.get(f"{BASE_URL}", params=params)
    response.raise_for_status()
    return response.json()

async def trends_logic(
    lens: str, trend_interval: str, trend_depth: int, sub_lens: Optional[str], 
    sub_lens_depth: int, focus: Optional[str], **filters
) -> Any:
    params = build_params(**filters)
    params.update({
        "lens": lens,
        "trend_interval": trend_interval,
        "trend_depth": trend_depth,
        "sub_lens": sub_lens,
        "sub_lens_depth": sub_lens_depth,
        "focus": focus
    })
    response = requests.get(f"{BASE_URL}trends", params=params)
    response.raise_for_status()
    return response.json()

async def geo_logic(**filters) -> Any:
    params = build_params(**filters)
    response = requests.get(f"{BASE_URL}geo/states", params=params)
    response.raise_for_status()
    return response.json()

async def suggest_logic(field: str, text: str, size: int) -> Any:
    params = {"text": text, "size": size}
    endpoint = "_suggest_company" if field == "company" else "_suggest_zip"
    response = requests.get(f"{BASE_URL}{endpoint}", params=params)
    response.raise_for_status()
    return response.json()

async def document_logic(complaint_id: str) -> Any:
    response = requests.get(f"{BASE_URL}{complaint_id}")
    response.raise_for_status()
    return response.json()

# -------------------------------------------------------------------------
# 3. Interface A: MCP Tools (For Anthropic/Claude Desktop)
# -------------------------------------------------------------------------

# We define wrapper functions for MCP to preserve the nice docstrings and type hints
# that the MCP SDK uses to generate the schema for the LLM.

@server.tool()
async def search_complaints(
    search_term: Optional[str] = None,
    field: str = "complaint_what_happened",
    size: int = 10,
    from_index: int = 0,
    sort: str = "relevance_desc",
    search_after: Optional[str] = None,
    no_highlight: bool = False,
    company: Optional[List[str]] = None,
    company_public_response: Optional[List[str]] = None,
    company_response: Optional[List[str]] = None,
    consumer_consent_provided: Optional[List[str]] = None,
    consumer_disputed: Optional[List[str]] = None,
    date_received_min: Optional[str] = None,
    date_received_max: Optional[str] = None,
    company_received_min: Optional[str] = None,
    company_received_max: Optional[str] = None,
    has_narrative: Optional[List[str]] = None,
    issue: Optional[List[str]] = None,
    product: Optional[List[str]] = None,
    state: Optional[List[str]] = None,
    submitted_via: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    timely: Optional[List[str]] = None,
    zip_code: Optional[List[str]] = None
) -> Any:
    """Search the Consumer Complaint Database."""
    return await search_logic(
        size, from_index, sort, search_after, no_highlight,
        search_term=search_term, field=field, company=company, 
        company_public_response=company_public_response, company_response=company_response,
        consumer_consent_provided=consumer_consent_provided, consumer_disputed=consumer_disputed,
        date_received_min=date_received_min, date_received_max=date_received_max,
        company_received_min=company_received_min, company_received_max=company_received_max,
        has_narrative=has_narrative, issue=issue, product=product, state=state,
        submitted_via=submitted_via, tags=tags, timely=timely, zip_code=zip_code
    )

@server.tool()
async def list_complaint_trends(
    lens: str = "overview",
    trend_interval: str = "month",
    trend_depth: int = 5,
    sub_lens: Optional[str] = None,
    sub_lens_depth: int = 5,
    focus: Optional[str] = None,
    search_term: Optional[str] = None,
    field: str = "complaint_what_happened",
    company: Optional[List[str]] = None,
    company_public_response: Optional[List[str]] = None,
    company_response: Optional[List[str]] = None,
    consumer_consent_provided: Optional[List[str]] = None,
    consumer_disputed: Optional[List[str]] = None,
    date_received_min: Optional[str] = None,
    date_received_max: Optional[str] = None,
    has_narrative: Optional[List[str]] = None,
    issue: Optional[List[str]] = None,
    product: Optional[List[str]] = None,
    state: Optional[List[str]] = None,
    submitted_via: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    timely: Optional[List[str]] = None,
    zip_code: Optional[List[str]] = None
) -> Any:
    """Get aggregated trend data for complaints over time."""
    return await trends_logic(
        lens, trend_interval, trend_depth, sub_lens, sub_lens_depth, focus,
        search_term=search_term, field=field, company=company, 
        company_public_response=company_public_response, company_response=company_response,
        consumer_consent_provided=consumer_consent_provided, consumer_disputed=consumer_disputed,
        date_received_min=date_received_min, date_received_max=date_received_max,
        # Trends usually ignore company_received dates in standard UI usage, passing None
        company_received_min=None, company_received_max=None,
        has_narrative=has_narrative, issue=issue, product=product, state=state,
        submitted_via=submitted_via, tags=tags, timely=timely, zip_code=zip_code
    )

@server.tool()
async def get_state_aggregations(
    search_term: Optional[str] = None,
    field: str = "complaint_what_happened",
    company: Optional[List[str]] = None,
    company_public_response: Optional[List[str]] = None,
    company_response: Optional[List[str]] = None,
    consumer_consent_provided: Optional[List[str]] = None,
    consumer_disputed: Optional[List[str]] = None,
    date_received_min: Optional[str] = None,
    date_received_max: Optional[str] = None,
    has_narrative: Optional[List[str]] = None,
    issue: Optional[List[str]] = None,
    product: Optional[List[str]] = None,
    state: Optional[List[str]] = None,
    submitted_via: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    timely: Optional[List[str]] = None,
    zip_code: Optional[List[str]] = None
) -> Any:
    """Get complaint counts aggregated by US State."""
    return await geo_logic(
        search_term=search_term, field=field, company=company, 
        company_public_response=company_public_response, company_response=company_response,
        consumer_consent_provided=consumer_consent_provided, consumer_disputed=consumer_disputed,
        date_received_min=date_received_min, date_received_max=date_received_max,
        company_received_min=None, company_received_max=None,
        has_narrative=has_narrative, issue=issue, product=product, state=state,
        submitted_via=submitted_via, tags=tags, timely=timely, zip_code=zip_code
    )

@server.tool()
async def get_complaint_document(complaint_id: str) -> Any:
    """Retrieve a single complaint by its ID."""
    return await document_logic(complaint_id)

@server.tool()
async def suggest_filter_values(field: str, text: str, size: int = 10) -> Any:
    """Autocomplete helper for filter values (company or zip)."""
    return await suggest_logic(field, text, size)

# -------------------------------------------------------------------------
# 4. Interface B: Standard REST API (For OpenAI/ChatGPT Actions)
# -------------------------------------------------------------------------

# We map FastAPI routes to the same logic functions.
# Note: FastAPI's dependency injection (Query) allows us to parse list params correctly from URL query strings.

@app.get("/search", operation_id="searchComplaints", summary="Search Complaints")
async def search_route(
    search_term: Optional[str] = None,
    field: str = "complaint_what_happened",
    size: int = 10,
    from_index: int = 0,
    sort: str = "relevance_desc",
    search_after: Optional[str] = None,
    no_highlight: bool = False,
    company: Optional[List[str]] = Query(None),
    company_public_response: Optional[List[str]] = Query(None),
    company_response: Optional[List[str]] = Query(None),
    consumer_consent_provided: Optional[List[str]] = Query(None),
    consumer_disputed: Optional[List[str]] = Query(None),
    date_received_min: Optional[str] = None,
    date_received_max: Optional[str] = None,
    company_received_min: Optional[str] = None,
    company_received_max: Optional[str] = None,
    has_narrative: Optional[List[str]] = Query(None),
    issue: Optional[List[str]] = Query(None),
    product: Optional[List[str]] = Query(None),
    state: Optional[List[str]] = Query(None),
    submitted_via: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    timely: Optional[List[str]] = Query(None),
    zip_code: Optional[List[str]] = Query(None)
):
    """REST Endpoint for searching complaints."""
    return await search_logic(
        size, from_index, sort, search_after, no_highlight,
        search_term=search_term, field=field, company=company, 
        company_public_response=company_public_response, company_response=company_response,
        consumer_consent_provided=consumer_consent_provided, consumer_disputed=consumer_disputed,
        date_received_min=date_received_min, date_received_max=date_received_max,
        company_received_min=company_received_min, company_received_max=company_received_max,
        has_narrative=has_narrative, issue=issue, product=product, state=state,
        submitted_via=submitted_via, tags=tags, timely=timely, zip_code=zip_code
    )

@app.get("/trends", operation_id="listTrends", summary="List Complaint Trends")
async def trends_route(
    lens: str = "overview",
    trend_interval: str = "month",
    trend_depth: int = 5,
    sub_lens: Optional[str] = None,
    sub_lens_depth: int = 5,
    focus: Optional[str] = None,
    search_term: Optional[str] = None,
    field: str = "complaint_what_happened",
    company: Optional[List[str]] = Query(None),
    company_public_response: Optional[List[str]] = Query(None),
    company_response: Optional[List[str]] = Query(None),
    consumer_consent_provided: Optional[List[str]] = Query(None),
    consumer_disputed: Optional[List[str]] = Query(None),
    date_received_min: Optional[str] = None,
    date_received_max: Optional[str] = None,
    has_narrative: Optional[List[str]] = Query(None),
    issue: Optional[List[str]] = Query(None),
    product: Optional[List[str]] = Query(None),
    state: Optional[List[str]] = Query(None),
    submitted_via: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    timely: Optional[List[str]] = Query(None),
    zip_code: Optional[List[str]] = Query(None)
):
    """REST Endpoint for retrieving trends."""
    return await trends_logic(
        lens, trend_interval, trend_depth, sub_lens, sub_lens_depth, focus,
        search_term=search_term, field=field, company=company, 
        company_public_response=company_public_response, company_response=company_response,
        consumer_consent_provided=consumer_consent_provided, consumer_disputed=consumer_disputed,
        date_received_min=date_received_min, date_received_max=date_received_max,
        company_received_min=None, company_received_max=None,
        has_narrative=has_narrative, issue=issue, product=product, state=state,
        submitted_via=submitted_via, tags=tags, timely=timely, zip_code=zip_code
    )

@app.get("/geo/states", operation_id="getGeoStates", summary="Get State Aggregations")
async def geo_route(
    search_term: Optional[str] = None,
    field: str = "complaint_what_happened",
    company: Optional[List[str]] = Query(None),
    company_public_response: Optional[List[str]] = Query(None),
    company_response: Optional[List[str]] = Query(None),
    consumer_consent_provided: Optional[List[str]] = Query(None),
    consumer_disputed: Optional[List[str]] = Query(None),
    date_received_min: Optional[str] = None,
    date_received_max: Optional[str] = None,
    has_narrative: Optional[List[str]] = Query(None),
    issue: Optional[List[str]] = Query(None),
    product: Optional[List[str]] = Query(None),
    state: Optional[List[str]] = Query(None),
    submitted_via: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    timely: Optional[List[str]] = Query(None),
    zip_code: Optional[List[str]] = Query(None)
):
    """REST Endpoint for geographic aggregations."""
    return await geo_logic(
        search_term=search_term, field=field, company=company, 
        company_public_response=company_public_response, company_response=company_response,
        consumer_consent_provided=consumer_consent_provided, consumer_disputed=consumer_disputed,
        date_received_min=date_received_min, date_received_max=date_received_max,
        company_received_min=None, company_received_max=None,
        has_narrative=has_narrative, issue=issue, product=product, state=state,
        submitted_via=submitted_via, tags=tags, timely=timely, zip_code=zip_code
    )

@app.get("/complaint/{complaint_id}", operation_id="getComplaintDocument", summary="Get Complaint Document")
async def document_route(complaint_id: str = Path(..., description="The ID of the complaint to retrieve")):
    """REST Endpoint for retrieving a single complaint."""
    return await document_logic(complaint_id)

@app.get("/suggest/{field}", operation_id="suggestFilterValues", summary="Suggest Filter Values")
async def suggest_route(
    field: str = Path(..., regex="^(company|zip_code)$"),
    text: str = Query(..., min_length=1),
    size: int = 10
):
    """REST Endpoint for autosuggestions."""
    return await suggest_logic(field, text, size)

# -------------------------------------------------------------------------
# 5. Application Mount & Run
# -------------------------------------------------------------------------

# Mount the MCP server endpoint
app.mount("/mcp", server.fastapi_app())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

```

### How to Connect

#### 1. Anthropic (Claude Desktop)

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cfpb-complaints": {
      "url": "http://localhost:8000/mcp/sse",
      "type": "sse"
    }
  }
}

```

#### 2. OpenAI (ChatGPT Actions)

1. Expose your server to the internet (e.g., `ngrok http 8000`).
2. In the "Create GPT" interface, click **Create new Action**.
3. Use the `openapi.json` automatically generated by FastAPI:
   `https://<your-ngrok-url>/openapi.json`
4. ChatGPT will now see the endpoints (`/search`, `/trends`, etc.) defined in the Python code above.
