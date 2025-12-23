I'll rewrite the bug report with the actual snake\_case tool names.

## Tool Call Details

### Call 1: Basic forbearance search

**Tool:** `search_complaints`
**JSON Sent:**

```json
{
  "search_term": "forbearance",
  "size": 10
}
```

**Response Received:**

```
<system>Tool ran without output or errors</system>
```

### Call 2: Forbearance search filtered by Mortgage product

**Tool:** `search_complaints`
**JSON Sent:**

```json
{
  "product": ["Mortgage"],
  "search_term": "forbearance",
  "size": 10
}
```

**Response Received:**

```
<system>Tool ran without output or errors</system>
```

### Call 3: Basic search with no filters (connectivity test)

**Tool:** `search_complaints`
**JSON Sent:**

```json
{
  "size": 5
}
```

**Response Received:**

```
<system>Tool ran without output or errors</system>
```

### Call 4: List complaint trends by product

**Tool:** `list_complaint_trends`
**JSON Sent:**

```json
{
  "lens": "product",
  "trend_depth": 6
}
```

**Response Received:**

```
400: {"non_field_errors":["Either Focus or Sub-lens is required for lens 'product'. Valid sub-lens are: ('sub_product', 'issue', 'company', 'tags')"]}
```

### Call 5: List complaint trends with sub\_lens

**Tool:** `list_complaint_trends`
**JSON Sent:**

```json
{
  "lens": "product",
  "search_term": "forbearance",
  "sub_lens": "issue",
  "trend_depth": 12
}
```

**Response Received:**

```
<system>Tool ran without output or errors</system>
```

### Call 6: Get overall trend signals

**Tool:** `get_overall_trend_signals`
**JSON Sent:**

```json
{
  "search_term": "forbearance",
  "trend_depth": 12
}
```

**Response Received:**

```
<system>Tool ran without output or errors</system>
```

### Call 7: Suggest filter values (autocomplete test)

**Tool:** `suggest_filter_values`
**JSON Sent:**

```json
{
  "field": "company",
  "text": "wells"
}
```

**Response Received:**

```
<system>Tool ran without output or errors</system>
```

***

## Bug Report: CFPB MCP Server Tool Calls Returning No Output

**Date:** December 22, 2025\
**Reporter:** Jim Moffet\
**Environment:** Claude.ai with CFPB Complaints Database Search MCP connector\
**Severity:** High - Complete tool functionality failure

### Summary

All CFPB MCP server tool calls are completing without errors but returning no data to Claude. The system reports `<system>Tool ran without output or errors</system>` for all successful calls, making the tools completely non-functional despite being properly registered and accepting requests.

### Expected Behavior

Tool calls should return JSON-formatted data containing complaint records, trend data, aggregations, or autocomplete suggestions based on the endpoint called.

### Actual Behavior

All tool calls return silently with no output. The only exception was one validation error (Call 4 using `list_complaint_trends`), which correctly returned a 400 error with proper JSON error message, proving the server is receiving requests and can respond with structured data.

### Evidence of Server Responsiveness

* **Call 4** (`list_complaint_trends` with invalid parameters) returned a proper 400 validation error with detailed JSON message about missing required parameters
* This proves:
  * The MCP server is running and receiving requests
  * The server can validate inputs
  * The server can return structured JSON responses
  * Authentication (if required) is working

### Reproduction Steps

1. Connect to CFPB Complaints Database Search MCP connector in Claude.ai
2. Invoke any tool with valid parameters
3. Observe that call completes without errors but returns no data

### Tools Tested (All Failed to Return Data)

1. **`search_complaints`** - Tested 3 times with:
   * Search term only ("forbearance")
   * Search term + product filter (\["Mortgage"])
   * Minimal parameters (size only)

2. **`list_complaint_trends`** - Tested with:
   * Invalid parameters (returned proper error - this worked!)
   * Valid parameters with lens="product", sub\_lens="issue", search term

3. **`get_overall_trend_signals`** - Tested with:
   * Search term and trend\_depth parameters

4. **`suggest_filter_values`** - Tested with:
   * field="company", text="wells"

### Diagnostic Analysis

**What's Working:**

* MCP server connectivity
* Request routing to all tested tools
* Parameter validation (evidenced by `list_complaint_trends` error)
* Error response formatting

**What's Broken:**

* Successful response data transmission for all tools
* Data serialization/formatting for successful responses
* Response streaming for data payloads

### Potential Root Causes

1. **Response Streaming Issue**
   * Server may be using SSE (Server-Sent Events) streaming that isn't being properly consumed
   * HTTP streaming implementation may not be flushing/closing connections properly
   * Response chunks may not be formatted correctly for Claude's MCP client

2. **Data Serialization Problem**
   * Successful responses may be returning data in a format Claude can't parse
   * JSON serialization may be failing silently for large payloads
   * Response may be missing required MCP protocol wrapper/envelope

3. **Empty Result Sets**
   * Less likely since even `suggest_filter_values` with "wells" should return Wells Fargo
   * Empty results should still return structured JSON like `{"results": [], "total": 0}`

4. **OAuth/Authentication Token Scope**
   * Token may have read permissions but responses are being filtered out
   * Silent authorization failure on data retrieval (but not on endpoint access)

### Recommended Investigation Steps

1. **Check Server Logs**
   * Look for successful 200 responses for `search_complaints`, `get_overall_trend_signals`, and `suggest_filter_values`
   * Check response body sizes (0 bytes = serialization failure)
   * Review any streaming-related log messages

2. **Test Direct API Calls**
   * Use curl/httpie to call endpoints directly for each tool
   * Compare direct response format to MCP protocol requirements
   * Verify responses contain actual data

3. **Review MCP Response Format**
   * Ensure responses follow MCP protocol specification for all tools
   * Check that content is wrapped in proper MCP message structure
   * Verify JSON serialization for successful responses matches error response format (from `list_complaint_trends`)

4. **HTTP Streaming Configuration**
   * Review SSE implementation if using Server-Sent Events
   * Check response chunking and connection closing
   * Verify Content-Type headers for streaming vs. standard JSON

5. **Compare with Working MCP Servers**
   * Review implementation differences with known-working MCP servers
   * Check if successful responses need different handling than errors
   * Note that error response from `list_complaint_trends` worked correctly

### Priority

This is a complete functionality failure - while the validation error in `list_complaint_trends` (Call 4) shows promise, no actual data can be retrieved from any tool. This should be treated as a P0/blocking issue for the CFPB MCP connector.

### Additional Context

Given recent work on OAuth authentication and HTTP streaming for this server, the issue likely relates to how successful data responses are streamed/formatted rather than basic connectivity or authentication. The fact that `list_complaint_trends` can return a properly formatted error response suggests the issue is specifically with how successful data payloads are being transmitted.
