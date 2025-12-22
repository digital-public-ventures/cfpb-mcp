# CFPB MCP Tool Descriptions: Before & After

## What Agents Don't See (Pre-Call Blind Spots)

Before making any tool calls, agents receive only the tool name, description, and JSON schema. Here's what's missing:

1. **No example values for parameters** - Agents don't know what valid `product` strings look like. Is it `"Mortgage"` or `"mortgage"` or `"Mortgage loans"`? They must guess or make a discovery call.

2. **No example responses** - Agents have no idea what the return shape is. Will they get `{hits: [...]}` or `{data: {hits: [...]}, citations: [...]}` or something else?

3. **No guidance on which tool to use when** - Terse descriptions like "Search the Consumer Complaint Database" vs "Get aggregated trend data" don't explain when one is preferable.

4. **No information about response size** - Agents don't know that some calls return 50KB by default while others return 200 bytes.

5. **No semantic information about filter values** - What are valid `tags` values? What does `lens` accept? The schema says `"type": "string"` but doesn't enumerate options.

6. **No relationship between tools** - Agents don't know that `get_complaint_document` is the "drill down" after `search_complaints`, or that `rank_company_spikes` internally calls multiple endpoints.

7. **No guidance on iterative workflows** - Nothing tells agents "start with count, then search, then get\_document."

***

## Tool Descriptions: Before & After

### 1. `count_complaints` (NEW)

**Before:** *(Did not exist)*

**After:**

```
Fast count of complaints matching filters. Returns ~200 bytes.

Use this FIRST to check if data exists and gauge result set size before 
fetching actual complaints. Returns: {count, has_narratives, search_url}

Example: count_complaints(product=["Mortgage"], state=["CA"]) → {count: 45892, ...}

For actual complaint records, use search_complaints after confirming count.
```

***

### 2. `search_complaints`

**Before:**

```
Search the Consumer Complaint Database.
```

**After:**

```
Search complaints and return matching records. Optimized for token efficiency.

DEFAULTS (designed for iterative exploration):
- size=3 (request more with size=10, 25, etc.)
- Narratives truncated to 500 chars (use get_complaint_document for full text)
- No aggregations (add include_aggregations=true if needed)

MODES:
- count_only=true → Just get count (~200 bytes). Fastest option.
- Default → Returns 3 complaints with truncated narratives (~2-5KB)
- include_aggregations=true → Adds facet counts by product/company/etc (~20KB extra)

RETURNS: {citations: [...], data: {hits: {total, hits: [...]}}}

WORKFLOW: count_complaints → search_complaints(size=3) → get_complaint_document(id)

FILTER VALUES (case-sensitive):
- product: "Mortgage", "Credit card", "Student loan", "Vehicle loan or lease", 
  "Credit reporting, credit repair services, or other personal consumer reports"
- state: Two-letter codes ("CA", "TX", "NY")
- tags: "Servicemember", "Older American"
- company_response: "Closed with monetary relief", "Closed with explanation"
- has_narrative: ["true"] or ["false"]
```

***

### 3. `get_complaint_document`

**Before:**

```
Retrieve a single complaint by its ID.
```

**After:**

```
Get full details for ONE complaint by ID, including complete narrative text.

Use after search_complaints to retrieve full narratives. Search results truncate
narratives to 500 chars; this returns the complete text (can be 2000+ words).

RETURNS: Full complaint record with all fields including untruncated 
complaint_what_happened narrative.

WORKFLOW: search_complaints → find relevant complaint_id → get_complaint_document(id)

Example: get_complaint_document(complaint_id="9233034")
```

***

### 4. `list_complaint_trends`

**Before:**

```
Get aggregated trend data for complaints over time.
```

**After:**

```
Get complaint volume over time, grouped by product/company/issue/etc.

Use for questions like "how have mortgage complaints changed over time?" or
"which products are growing fastest?"

KEY PARAMETERS:
- lens: "overview" (total only), "product", "company", "issue" 
- trend_interval: "month", "week", "day", "year"
- trend_depth: Number of periods to return (default 5)
- sub_lens: Add second grouping level (increases response size significantly)

RETURNS: {citations: [...], data: {aggregations: {dateRangeArea: {buckets: [...]}}}}
Each bucket has: {key_as_string: "2024-01", doc_count: 1234}

For spike detection with statistical signals, use get_overall_trend_signals or
rank_group_spikes instead—they compute z-scores and ratios for you.

COMMON PATTERNS:
- Overall trend: lens="overview", trend_depth=12
- By product: lens="product", trend_depth=6
- Single company: lens="overview", company=["WELLS FARGO"]
```

***

### 5. `get_overall_trend_signals`

**Before:**

```
Compute simple spike/velocity signals from upstream overall trends buckets.
```

**After:**

```
Detect unusual complaint volume changes with statistical signals.

Computes z-scores and ratios comparing the latest period against a baseline.
Use for "are complaints spiking?" or "is this month unusual?"

RETURNS pre-computed signals:
- last_vs_prev: Change from previous period (absolute + percentage)
- last_vs_baseline: Z-score and ratio vs trailing average
  - z > 2.0 suggests statistically significant spike
  - ratio > 1.5 means 50% above baseline

KEY PARAMETERS:
- baseline_window: Periods to average for baseline (default 8)
- min_baseline_mean: Minimum avg complaints to compute stats (default 10)
- trend_interval: "month", "week" (default "month")

RETURNS: {params: {...}, signals: {overall: {last_bucket, prev_bucket, signals: {...}}}}

Use rank_company_spikes or rank_group_spikes to find WHICH companies/products
are spiking, not just whether overall volume is unusual.
```

***

### 6. `rank_company_spikes`

**Before:**

```
Pipeline-style company spikes: search aggs -> top companies -> trends per company -> rank.
```

**After:**

```
Find companies with unusual complaint spikes, ranked by statistical significance.

Automatically: (1) finds top companies by volume, (2) computes trend for each,
(3) calculates z-scores, (4) ranks by spike severity.

Use for: "Which companies are seeing complaint surges?" or regulatory monitoring.

KEY PARAMETERS:
- top_n: How many companies to analyze (default 10)
- baseline_window: Periods for baseline average (default 8)
- min_baseline_mean: Minimum complaints to include (default 25, filters noise)

RETURNS: {results: [{company, company_doc_count, computed: {signals: {last_vs_baseline: {z, ratio}}}}]}

Companies with z > 2.0 are experiencing statistically unusual spikes.

NOTE: This makes multiple upstream API calls internally. May take 5-10 seconds.
For issue/product spikes instead of company, use rank_group_spikes.
```

***

### 7. `rank_group_spikes`

**Before:**

```
Rank group values (e.g., products or issues) by latest-bucket spike.
```

**After:**

```
Find products or issues with unusual complaint spikes, ranked by severity.

Like rank_company_spikes but for product categories or issue types.

REQUIRED PARAMETER:
- group: "product" or "issue"

KEY PARAMETERS:
- top_n: How many to return (default 10)
- baseline_window: Periods for baseline (default 8)
- min_baseline_mean: Minimum volume threshold (default 10)

RETURNS: {results: [{group: "Credit reporting...", doc_count, signals: {last_vs_baseline: {z, ratio}}}]}

Items with z > 2.0 are spiking unusually. Use for "which issue types are surging?"

Can combine with filters: rank_group_spikes(group="issue", company=["NAVIENT"])
→ "Which issues are spiking for Navient specifically?"
```

***

### 8. `get_state_aggregations`

**Before:**

```
Get complaint counts aggregated by US State.
```

**After:**

```
Get complaint counts broken down by US state. Returns all 50 states + territories.

Use for geographic analysis: "Which states have the most mortgage complaints?"
or "Compare complaint volume across states for Company X."

RETURNS: {citations: [...], data: {aggregations: {state: {buckets: [
  {key: "FL", doc_count: 45000},
  {key: "CA", doc_count: 42000},
  ...
]}}}}

Buckets are sorted by doc_count descending (highest volume states first).

Combine with filters for focused analysis:
- By product: get_state_aggregations(product=["Student loan"])
- By company: get_state_aggregations(company=["BANK OF AMERICA"])
- By date: get_state_aggregations(date_received_min="2024-01-01")
```

***

### 9. `suggest_filter_values`

**Before:**

```
Autocomplete helper for filter values (company or zip_code).
```

**After:**

```
Autocomplete for company names or zip codes. Use when you don't know exact spelling.

Company names must match exactly in filters. This finds the canonical name.

REQUIRED PARAMETERS:
- field: "company" or "zip_code"  
- text: Partial text to match

RETURNS: Array of matching values, e.g.:
  suggest_filter_values(field="company", text="wells") 
  → ["WELLS FARGO & COMPANY", "WELLS FARGO BANK, N.A.", ...]

Use the returned exact string in subsequent search_complaints or other filters.

Example workflow:
1. suggest_filter_values(field="company", text="navient") → ["NAVIENT SOLUTIONS, LLC."]
2. search_complaints(company=["NAVIENT SOLUTIONS, LLC."])
```

***

### 10. `generate_cfpb_dashboard_url`

**Before:**

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

**After:**

```
Generate a URL to the official CFPB dashboard with filters pre-applied.

Use to give users a clickable link to explore data themselves on consumerfinance.gov.
The official dashboard has interactive charts, maps, and full complaint browser.

RETURNS: URL string like "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?..."

Perfect for:
- Citing your data source authoritatively
- Letting users explore beyond what you've summarized
- Sharing filtered views (e.g., "all crypto complaints in 2024")

NOTE: All search/trend tools already include citations with dashboard URLs in their
response. Use this tool only when you need a standalone URL without running a query.
```

***

### 11. `capture_cfpb_chart_screenshot`

**Before:**

```
Capture a screenshot of the official CFPB trends chart as a PNG image.
```

**After:**

```
Capture a screenshot of the CFPB trends chart as a base64-encoded PNG.

Renders the official consumerfinance.gov visualization and captures the chart.
Use when users need a visual/image rather than raw data.

KEY PARAMETERS:
- lens: What to group by - "Product", "Company", "Issue" (default "Product")
- chart_type: "line" or "area" (default "line")
- date_interval: "Month", "Week", "Day", "Year" (default "Month")

RETURNS: Base64-encoded PNG string. Decode to display or save as image.

Takes 5-10 seconds (loads real browser, waits for chart render).

NOTE: Requires Playwright. Returns error if screenshot service unavailable.
For data analysis, use list_complaint_trends instead—it's faster and returns
structured data you can process.
```

***

## Recommended Workflow Patterns

Include these in a system prompt or documentation:

```
CFPB DATA WORKFLOWS:

1. EXISTENCE CHECK
   count_complaints(filters...) → {count: N}
   
2. QUICK SCAN  
   search_complaints(size=3) → See a few examples
   
3. DEEP DIVE
   get_complaint_document(complaint_id) → Full narrative text
   
4. TREND ANALYSIS
   list_complaint_trends(lens="product") → Volume over time
   
5. SPIKE DETECTION
   rank_company_spikes() → Which companies are surging?
   rank_group_spikes(group="issue") → Which issues are surging?

6. GEOGRAPHIC BREAKDOWN
   get_state_aggregations(product=["Mortgage"]) → By state

7. FIND EXACT COMPANY NAME
   suggest_filter_values(field="company", text="chase") → Canonical name
```
