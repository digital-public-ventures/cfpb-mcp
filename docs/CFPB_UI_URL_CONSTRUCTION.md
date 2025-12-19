# CFPB Consumer Complaints UI URL Construction Guide

## Base URL

```
https://www.consumerfinance.gov/data-research/consumer-complaints/search/
```

## Reference URL (Complex Example)

This real-world URL demonstrates all major parameters:

```
https://www.consumerfinance.gov/data-research/consumer-complaints/search/?chartType=line&company_public_response=Company%20has%20responded%20to%20the%20consumer%20and%20the%20CFPB%20and%20chooses%20not%20to%20provide%20a%20public%20response&company_public_response=Company%20believes%20it%20acted%20appropriately%20as%20authorized%20by%20contract%20or%20law&company_public_response=Company%20believes%20the%20complaint%20provided%20an%20opportunity%20to%20answer%20consumer%27s%20questions&company_public_response=Company%20believes%20complaint%20is%20the%20result%20of%20an%20isolated%20error&company_response=Closed%20with%20explanation&company_response=Closed%20with%20non-monetary%20relief&dateInterval=Month&date_received_max=2025-12-18&date_received_min=2019-12-18&has_narrative=true&issue=Trouble%20during%20payment%20process&issue=Applying%20for%20a%20mortgage%20or%20refinancing%20an%20existing%20mortgage&lens=Product&product=Mortgage&product=Debt%20collection&product=Credit%20reporting%2C%20credit%20repair%20services%2C%20or%20other%20personal%20consumer%20reports&searchField=all&searchText=mortgage%20scam&state=TX&state=FL&state=CA&state=NY&state=IL&subLens=sub_product&tab=Trends&tags=Older%20American&tags=Servicemember&tags=Older%20American%2C%20Servicemember
```

## URL Parameter Reference

### UI Display Parameters

| Parameter | Type | Values | Description | Notes |
|-----------|------|--------|-------------|-------|
| `tab` | string | `List`, `Trends`, `Map` | Which tab/view to display | Default: `List` |
| `chartType` | string | `line`, `area` | Chart visualization type | Only applicable when `tab=Trends` |
| `lens` | string | `Overview`, `Company`, `Product` | Aggregation dimension for trends | Only applicable when `tab=Trends` |
| `subLens` | string | `sub_product`, `issue`, etc. | Secondary aggregation dimension | Hierarchical drill-down |
| `dateInterval` | string | `Day`, `Week`, `Month`, `Quarter`, `Year` | Time grouping for trends | Default: `Month` |

### Search & Filter Parameters

| Parameter | Type | Values | Description | Notes |
|-----------|------|--------|-------------|-------|
| `searchText` | string | Any text | Search query term | URL-encoded |
| `searchField` | string | `all`, `complaint_what_happened`, `company` | Field to search within | Default: `all` |
| `date_received_min` | date | `YYYY-MM-DD` | Start date (inclusive) | ISO 8601 format |
| `date_received_max` | date | `YYYY-MM-DD` | End date (inclusive) | ISO 8601 format |
| `company_received_min` | date | `YYYY-MM-DD` | Date CFPB sent complaint to company (start) | |
| `company_received_max` | date | `YYYY-MM-DD` | Date CFPB sent complaint to company (end) | |

### Multi-Value Filter Parameters

These parameters can be repeated for multiple selections:

| Parameter | Type | Example Values | Description |
|-----------|------|----------------|-------------|
| `product` | string\[] | `Mortgage`, `Debt collection`, `Credit reporting, credit repair services, or other personal consumer reports` | Product type filters |
| `issue` | string\[] | `Trouble during payment process`, `Applying for a mortgage or refinancing an existing mortgage` | Issue type filters |
| `state` | string\[] | `TX`, `FL`, `CA`, `NY`, `IL` | State abbreviations (2-letter) |
| `company` | string\[] | `BANK OF AMERICA`, `WELLS FARGO & COMPANY` | Company name filters |
| `company_response` | string\[] | `Closed with explanation`, `Closed with non-monetary relief`, `Closed with monetary relief` | How company responded |
| `company_public_response` | string\[] | `Company has responded to the consumer and the CFPB and chooses not to provide a public response`, `Company believes it acted appropriately as authorized by contract or law` | Company's public statement |
| `tags` | string\[] | `Older American`, `Servicemember`, `Older American, Servicemember` | Consumer demographic tags |

### Boolean Filter Parameters

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `has_narrative` | boolean | `true`, `false` | Filter for complaints with consumer narratives |
| `consumer_disputed` | string | `yes`, `no` | Whether consumer disputed company response |
| `timely` | string | `yes`, `no` | Whether company responded in timely manner |

### Pagination & Sorting (List View)

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `page` | integer | 1, 2, 3... | Page number (1-indexed) |
| `size` | integer | 10, 25, 50, 100 | Results per page |
| `sort` | string | `relevance_desc`, `relevance_asc`, `created_date_desc`, `created_date_asc` | Sort order |
| `frm` | integer | 0, 25, 50... | Offset for pagination (0-indexed) |

### Export Parameters

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `format` | string | `json`, `csv` | Export format (when downloading) |

## URL Encoding Rules

1. **Spaces**: Encoded as `%20` (not `+`)
2. **Commas**: Encoded as `%2C`
3. **Apostrophes**: Encoded as `%27`
4. **Multi-values**: Repeat the same parameter multiple times
   * Example: `&product=Mortgage&product=Debt%20collection`
5. **Special characters**: Follow standard percent-encoding

## Construction Examples

### Example 1: Simple Search

```
/search/?searchText=foreclosure&date_received_min=2020-01-01&product=Mortgage
```

### Example 2: Trends View with Multiple Filters

```
/search/?tab=Trends&chartType=line&lens=Product&dateInterval=Month&date_received_min=2020-01-01&date_received_max=2024-12-31&state=CA&state=NY
```

### Example 3: List View with Narratives

```
/search/?tab=List&has_narrative=true&searchField=complaint_what_happened&searchText=fraud&page=1&size=25&sort=created_date_desc
```

### Example 4: Company-Specific Analysis

```
/search/?tab=Trends&lens=Company&company=WELLS%20FARGO%20%26%20COMPANY&dateInterval=Quarter&date_received_min=2019-01-01
```

### Example 5: Map View by State

```
/search/?tab=Map&product=Mortgage&issue=Trouble%20during%20payment%20process&date_received_min=2023-01-01
```

## Implementation Notes

### For MCP Server Citation URLs

When generating citation URLs for MCP server responses:

1. **Include all active filters**: Reconstruct the URL with all parameters used in the query
2. **Default to Trends view**: Use `tab=Trends` for analytical queries
3. **Default to List view**: Use `tab=List` for search/narrative queries
4. **Set appropriate date ranges**: Always include `date_received_min` and `date_received_max` when filtering by date
5. **URL-encode all values**: Use proper percent-encoding for spaces and special characters
6. **Preserve multi-values**: Repeat parameters for array-like filters

### URL Builder Pattern

```python
def build_citation_url(
    search_term: str | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    tab: str = "List",
    # ... other params
) -> str:
    """Build a CFPB UI citation URL from query parameters."""
    base = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/"
    params = []
    
    if tab:
        params.append(f"tab={tab}")
    if search_term:
        params.append(f"searchText={quote(search_term)}")
    if date_received_min:
        params.append(f"date_received_min={date_received_min}")
    if date_received_max:
        params.append(f"date_received_max={date_received_max}")
    if product:
        for p in product:
            params.append(f"product={quote(p)}")
    if state:
        for s in state:
            params.append(f"state={s}")
    
    if params:
        return f"{base}?{'&'.join(params)}"
    return base
```

## Known Parameter Values

### `searchField` Options

* `all` - Search all fields
* `complaint_what_happened` - Search narratives only
* `company` - Search company names only
* `company_public_response` - Search company responses

### `lens` Options

* `Overview` - Overall complaint volume
* `Company` - By company
* `Product` - By product type

### `dateInterval` Options

* `Day` - Daily aggregation (may be disabled for large ranges)
* `Week` - Weekly aggregation
* `Month` - Monthly aggregation (most common)
* `Quarter` - Quarterly aggregation
* `Year` - Yearly aggregation

### `chartType` Options

* `line` - Line chart (default)
* `area` - Area chart (stacked)

### Common `company_response` Values

* `Closed with explanation`
* `Closed with monetary relief`
* `Closed with non-monetary relief`
* `Closed with relief`
* `Closed without relief`
* `In progress`
* `Untimely response`

### Common `tags` Values

* `Older American` - Age 62+
* `Servicemember` - Military service member
* `Older American, Servicemember` - Both tags

## Comparison: UI vs API Parameters

| UI Parameter | API Parameter | Notes |
|--------------|---------------|-------|
| `searchText` | `search_term` | UI uses camelCase |
| `date_received_min` | `date_received_min` | Same in both |
| `date_received_max` | `date_received_max` | Same in both |
| `product` | `product` | Same in both |
| `state` | `state` | Same in both |
| `tab` | N/A | UI-only (display control) |
| `chartType` | N/A | UI-only (visualization) |
| `lens` | N/A | UI-only (aggregation view) |
| `dateInterval` | N/A | UI-only (time grouping) |

**Important**: The UI and API use **different parameter naming conventions** for some fields:

* UI search param: `searchText` (camelCase)
* API search param: `search_term` (snake\_case)
