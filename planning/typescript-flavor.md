This is a comprehensive migration guide designed for a Coding Agent (like GitHub Copilot Workspace, Cursor, or Windsurf) to execute the port from Python/FastAPI to TypeScript/Cloudflare Workers.

You can provide the prompt below directly to your coding agent.

***

# Migration Guide: Python FastMCP to Cloudflare Workers (TypeScript)

**Role:** Senior Full-Stack Engineer / System Architect
**Objective:** Port an existing Python FastMCP server (`server.py` and `deeplink_mapping.py`) to a TypeScript Cloudflare Worker using the `@modelcontextprotocol/sdk`.
**Constraint:** The user strictly requires **Streamable HTTP** (stateless HTTP POST for JSON-RPC), mirroring the source configuration. Do not implement a complex SSE handler unless the SDK enforces it for the specific transport.

## 1. Project Scaffolding & Dependencies

Initialize a new Cloudflare Worker project using `wrangler`.

**Dependencies:**

* `@modelcontextprotocol/sdk`: Core MCP logic.
* `zod`: For schema definition (replacing Python `dataclasses` and `type hints`).
* `date-fns`: For date manipulation (replacing Python `datetime`).
* `js-sha256`: For API key hashing (replacing Python `hashlib`).

**File Structure Target:**

```text
src/
├── index.ts                # Main worker entry point (Auth, Rate Limit, MCP wiring)
├── tools/
│   ├── definitions.ts      # Tool definitions (Zod schemas + Descriptions)
│   └── handlers.ts         # Tool execution logic (API calls, aggregations)
├── utils/
│   ├── deeplink.ts         # Port of deeplink_mapping.py
│   ├── math.ts             # Port of math/stats functions (_mean, _stddev, etc.)
│   ├── api.ts              # Upstream fetch wrappers (replacing httpx)
│   └── security.ts         # Rate limiting (TokenBucket) and Auth

```

***

## 2. Detailed Implementation Steps

### Step 1: Port `deeplink_mapping.py` to `src/utils/deeplink.ts`

**Source:** `deeplink_mapping.py`
**Instructions:**

1. Convert `API_TO_URL_PARAM`, `URL_TO_API_PARAM`, and the constant Sets (`SEARCH_ENDPOINT_KEYS`, etc.) to TypeScript `const` objects/Sets.
2. Port `_clean_value`, `_parse_int`, `_format_trend_interval`, and `_format_lens` to strict TypeScript functions.
3. Implement `apply_default_dates` using `date-fns` to replicate the "last day of the month before (today - 30 days)" logic.
4. Port `build_deeplink_url` and `url_params_to_api_params`.
5. **Critical:** Ensure URL encoding (`urlencode`) behaves identically to Python's implementation (handling repeated query params correctly).

### Step 2: Port Math & Signal Logic to `src/utils/math.ts`

**Source:** `server.py` (Functions: `_mean`, `_stddev`, `_extract_overall_points`, `_compute_simple_signals`, etc.)
**Instructions:**

1. Implement `mean` and `stddev` handling empty arrays safely (return 0.0).
2. Port `_compute_simple_signals`.

* **Note:** Python's `list[-1]` indexing must be converted to `array[array.length - 1]`.
* Ensure floating-point precision is handled standardly (JS `number` is sufficient).

3. Port the extraction logic (`_extract_group_series`, `_company_buckets_from_search`).

* These function parse deep JSON structures from the Elasticsearch/OpenSearch response. Use Optional Chaining (`?.`) heavily to prevent crashes on missing keys.

### Step 3: Implement Upstream API Client in `src/utils/api.ts`

**Source:** `server.py` (`search_logic`, `trends_logic`, `geo_logic`)
**Instructions:**

1. Create a `fetchCFPB` helper function.

* **Base URL:** `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/`
* Use the native `fetch` API.
* Convert the Python `prune_params` logic to remove `null`/`undefined` keys before creating `URLSearchParams`.

2. Replicate `_normalize_scalar` and `_normalize_list` to ensure boolean values become strings `"true"`/`"false"` for the upstream API.

### Step 4: Define Tools in `src/tools/`

**Source:** `server.py` (`@server.tool` decorated functions)
**Instructions:**

1. **Schema Conversion:** Convert Python type hints to Zod schemas.

* *Example:* `field: Literal['company', 'all']` → `z.enum(['company', 'all']).default('company')`.
* *Example:* `company: list[str] | None` → `z.array(z.string()).optional()`.

2. **Handlers:**

* Create the tool handlers in `handlers.ts`.
* Connect them to the `api.ts` functions.
* **Citations:** Port the `generate_citations` logic from `server.py`. This constructs the list of reference URLs returned in the MCP response.

### Step 5: Infrastructure (Auth & Rate Limit) in `src/utils/security.ts`

**Source:** `server.py` (`_TokenBucket`, `MCPAccessControlMiddleware`)
**Instructions:**

1. **Rate Limiter:** Port the `_TokenBucket` class.

* *Cloudflare Context:* Store these buckets in a `Map<string, TokenBucket>` at the module level.
* *Warning:* Acknowledge that this is ephemeral (resets on Worker eviction). This is acceptable for this migration, but ideally, use Cloudflare Rate Limiting logic if available in the environment.

2. **Auth:** Implement `validateApiKey(requestHeader, validKeysString)`.

* Split `validKeysString` by comma.
* Use `crypto.subtle.timingSafeEqual` (or a constant-time string comparison helper) to prevent timing attacks.

### Step 6: Main Worker Entry (`src/index.ts`)

**Source:** `server.py` (`app` setup, middleware, main entry)
**Instructions:**

1. Initialize `McpServer` from `@modelcontextprotocol/sdk/server/mcp.js`.
2. Register all tools from Step 4.
3. Export the `fetch` handler:

```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // 1. Path Check: Ensure path is /mcp
    const url = new URL(request.url);
    if (url.pathname !== '/mcp') return new Response('Not Found', { status: 404 });

    // 2. Auth Check (Port logic from MCPAccessControlMiddleware)
    const apiKey = request.headers.get('x-api-key');
    if (!validateApiKey(apiKey, env.CFPB_MCP_API_KEYS)) {
       return new Response('Unauthorized', { status: 401 });
    }

    // 3. Rate Limit Check
    if (!checkRateLimit(apiKey || 'anon', env)) {
       return new Response('Too Many Requests', { status: 429 });
    }

    // 4. Hand off to MCP
    // Use the SDK's transport mechanism or process the JSON-RPC body manually
    // depending on strict "Streamable HTTP" requirement.
    // Recommended: Use SSSE handling or standard POST processing provided by SDK utils.
  }
}

```

***

## 3. Key Differences / Gotchas

1. **Environment Variables:** In Python, you used `os.getenv`. In Cloudflare, access these via the `env` object passed to `fetch`.
2. **Global State:** The Python server relied on global locks for rate limiting. Cloudflare Workers are single-threaded per isolate but distributed. The in-memory rate limit will strictly enforce limits *per isolate*, not globally.
3. **Recursion/Loops:** TypeScript requires explicit typing for recursive search params cleaning.
4. **Citations:** Ensure the `generate_citations` function returns the exact JSON structure expected by the client, as this is a custom extension in your Python server.
