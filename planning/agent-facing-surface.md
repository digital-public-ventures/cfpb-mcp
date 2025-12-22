Great question. Here's exactly what I see in my context about the CFPB MCP tools. This is the complete surface area available to me before I make any calls:

***

## Tool 1: `cfpb-mcp-two:capture_cfpb_chart_screenshot`

**Description:**

```
Capture a screenshot of the official CFPB trends chart as a PNG image.
```

**Parameters (JSON Schema):**

```json
{
  "properties": {
    "chart_type": {"default": "line", "title": "Chart Type", "type": "string"},
    "company": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company"},
    "date_interval": {"default": "Month", "title": "Date Interval", "type": "string"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "lens": {"default": "Product", "title": "Lens", "type": "string"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"}
  },
  "title": "capture_cfpb_chart_screenshotArguments",
  "type": "object"
}
```

***

## Tool 2: `cfpb-mcp-two:generate_cfpb_dashboard_url`

**Description:**

```
Generate a deep-link URL to the official CFPB consumer complaints dashboard.

    This creates a URL pre-configured with filters matching your search criteria.
    Users can click the link to explore the official government visualization tool
    with charts, trends, and interactive data exploration.

    Perfect for:
    - Sharing pre-filtered complaint views
    - Providing authoritative, branded visualizations
    - Giving users access to the full official dashboard
```

**Parameters:**

```json
{
  "properties": {
    "company": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company"},
    "company_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Response"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "has_narrative": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Has Narrative"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"}
  },
  "title": "generate_cfpb_dashboard_urlArguments",
  "type": "object"
}
```

***

## Tool 3: `cfpb-mcp-two:get_complaint_document`

**Description:**

```
Retrieve a single complaint by its ID.
```

**Parameters:**

```json
{
  "properties": {
    "complaint_id": {"title": "Complaint Id", "type": "string"}
  },
  "required": ["complaint_id"],
  "title": "get_complaint_documentArguments",
  "type": "object"
}
```

***

## Tool 4: `cfpb-mcp-two:get_overall_trend_signals`

**Description:**

```
Compute simple spike/velocity signals from upstream overall trends buckets.
```

**Parameters:**

```json
{
  "properties": {
    "baseline_window": {"default": 8, "title": "Baseline Window", "type": "integer"},
    "company": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company"},
    "company_public_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Public Response"},
    "company_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Max"},
    "company_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Min"},
    "company_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Response"},
    "consumer_consent_provided": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Consent Provided"},
    "consumer_disputed": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Disputed"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "field": {"default": "complaint_what_happened", "enum": ["complaint_what_happened", "company", "all"], "title": "Field", "type": "string"},
    "has_narrative": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Has Narrative"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "lens": {"default": "overview", "title": "Lens", "type": "string"},
    "min_baseline_mean": {"default": 10, "title": "Min Baseline Mean", "type": "number"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"},
    "submitted_via": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Submitted Via"},
    "tags": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Tags"},
    "timely": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Timely"},
    "trend_depth": {"default": 24, "title": "Trend Depth", "type": "integer"},
    "trend_interval": {"default": "month", "title": "Trend Interval", "type": "string"},
    "zip_code": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Zip Code"}
  },
  "title": "get_overall_trend_signalsArguments",
  "type": "object"
}
```

***

## Tool 5: `cfpb-mcp-two:get_state_aggregations`

**Description:**

```
Get complaint counts aggregated by US State.
```

**Parameters:**

```json
{
  "properties": {
    "company": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company"},
    "company_public_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Public Response"},
    "company_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Max"},
    "company_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Min"},
    "company_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Response"},
    "consumer_consent_provided": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Consent Provided"},
    "consumer_disputed": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Disputed"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "field": {"default": "complaint_what_happened", "enum": ["complaint_what_happened", "company", "all"], "title": "Field", "type": "string"},
    "has_narrative": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Has Narrative"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"},
    "submitted_via": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Submitted Via"},
    "tags": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Tags"},
    "timely": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Timely"},
    "zip_code": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Zip Code"}
  },
  "title": "get_state_aggregationsArguments",
  "type": "object"
}
```

***

## Tool 6: `cfpb-mcp-two:list_complaint_trends`

**Description:**

```
Get aggregated trend data for complaints over time.
```

**Parameters:**

```json
{
  "properties": {
    "company": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company"},
    "company_public_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Public Response"},
    "company_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Max"},
    "company_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Min"},
    "company_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Response"},
    "consumer_consent_provided": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Consent Provided"},
    "consumer_disputed": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Disputed"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "field": {"default": "complaint_what_happened", "enum": ["complaint_what_happened", "company", "all"], "title": "Field", "type": "string"},
    "focus": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Focus"},
    "has_narrative": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Has Narrative"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "lens": {"default": "overview", "title": "Lens", "type": "string"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"},
    "sub_lens": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Sub Lens"},
    "sub_lens_depth": {"default": 5, "title": "Sub Lens Depth", "type": "integer"},
    "submitted_via": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Submitted Via"},
    "tags": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Tags"},
    "timely": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Timely"},
    "trend_depth": {"default": 5, "title": "Trend Depth", "type": "integer"},
    "trend_interval": {"default": "month", "title": "Trend Interval", "type": "string"},
    "zip_code": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Zip Code"}
  },
  "title": "list_complaint_trendsArguments",
  "type": "object"
}
```

***

## Tool 7: `cfpb-mcp-two:rank_company_spikes`

**Description:**

```
Pipeline-style company spikes: search aggs -> top companies -> trends per company -> rank.
```

**Parameters:**

```json
{
  "properties": {
    "baseline_window": {"default": 8, "title": "Baseline Window", "type": "integer"},
    "company_public_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Public Response"},
    "company_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Max"},
    "company_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Min"},
    "company_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Response"},
    "consumer_consent_provided": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Consent Provided"},
    "consumer_disputed": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Disputed"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "field": {"default": "complaint_what_happened", "enum": ["complaint_what_happened", "company", "all"], "title": "Field", "type": "string"},
    "has_narrative": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Has Narrative"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "lens": {"default": "overview", "title": "Lens", "type": "string"},
    "min_baseline_mean": {"default": 25, "title": "Min Baseline Mean", "type": "number"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"},
    "submitted_via": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Submitted Via"},
    "tags": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Tags"},
    "timely": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Timely"},
    "top_n": {"default": 10, "title": "Top N", "type": "integer"},
    "trend_depth": {"default": 12, "title": "Trend Depth", "type": "integer"},
    "trend_interval": {"default": "month", "title": "Trend Interval", "type": "string"},
    "zip_code": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Zip Code"}
  },
  "title": "rank_company_spikesArguments",
  "type": "object"
}
```

***

## Tool 8: `cfpb-mcp-two:rank_group_spikes`

**Description:**

```
Rank group values (e.g., products or issues) by latest-bucket spike.
```

**Parameters:**

```json
{
  "properties": {
    "baseline_window": {"default": 8, "title": "Baseline Window", "type": "integer"},
    "company": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company"},
    "company_public_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Public Response"},
    "company_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Max"},
    "company_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Min"},
    "company_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Response"},
    "consumer_consent_provided": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Consent Provided"},
    "consumer_disputed": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Disputed"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "field": {"default": "complaint_what_happened", "enum": ["complaint_what_happened", "company", "all"], "title": "Field", "type": "string"},
    "group": {"enum": ["product", "issue"], "title": "Group", "type": "string"},
    "has_narrative": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Has Narrative"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "lens": {"default": "overview", "title": "Lens", "type": "string"},
    "min_baseline_mean": {"default": 10, "title": "Min Baseline Mean", "type": "number"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"},
    "sub_lens_depth": {"default": 10, "title": "Sub Lens Depth", "type": "integer"},
    "submitted_via": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Submitted Via"},
    "tags": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Tags"},
    "timely": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Timely"},
    "top_n": {"default": 10, "title": "Top N", "type": "integer"},
    "trend_depth": {"default": 12, "title": "Trend Depth", "type": "integer"},
    "trend_interval": {"default": "month", "title": "Trend Interval", "type": "string"},
    "zip_code": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Zip Code"}
  },
  "required": ["group"],
  "title": "rank_group_spikesArguments",
  "type": "object"
}
```

***

## Tool 9: `cfpb-mcp-two:search_complaints`

**Description:**

```
Search the Consumer Complaint Database.
```

**Parameters:**

```json
{
  "properties": {
    "company": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company"},
    "company_public_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Public Response"},
    "company_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Max"},
    "company_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Company Received Min"},
    "company_response": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Company Response"},
    "consumer_consent_provided": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Consent Provided"},
    "consumer_disputed": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Consumer Disputed"},
    "date_received_max": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Max"},
    "date_received_min": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Date Received Min"},
    "field": {"default": "complaint_what_happened", "enum": ["complaint_what_happened", "company", "all"], "title": "Field", "type": "string"},
    "from_index": {"default": 0, "title": "From Index", "type": "integer"},
    "has_narrative": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Has Narrative"},
    "issue": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Issue"},
    "no_highlight": {"default": false, "title": "No Highlight", "type": "boolean"},
    "product": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Product"},
    "search_after": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search After"},
    "search_term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Search Term"},
    "size": {"default": 10, "title": "Size", "type": "integer"},
    "sort": {"default": "relevance_desc", "enum": ["relevance_desc", "created_date_desc"], "title": "Sort", "type": "string"},
    "state": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "State"},
    "submitted_via": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Submitted Via"},
    "tags": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Tags"},
    "timely": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Timely"},
    "zip_code": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": null, "title": "Zip Code"}
  },
  "title": "search_complaintsArguments",
  "type": "object"
}
```

***

## Tool 10: `cfpb-mcp-two:suggest_filter_values`

**Description:**

```
Autocomplete helper for filter values (company or zip_code).
```

**Parameters:**

```json
{
  "properties": {
    "field": {"enum": ["company", "zip_code"], "title": "Field", "type": "string"},
    "size": {"default": 10, "title": "Size", "type": "integer"},
    "text": {"title": "Text", "type": "string"}
  },
  "required": ["field", "text"],
  "title": "suggest_filter_valuesArguments",
  "type": "object"
}
```
