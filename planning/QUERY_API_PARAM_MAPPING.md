# URL Query Params to Complaints API Mapping (Partial)

This document summarizes how URL query parameters are parsed into Redux state
and then translated into CFPB complaints API request parameters. The mapping
here is intentionally partial and focuses on the deeplink/search flow.

## High-level flow

1. URL query params are parsed with `query-string` and sent to
   `routes/routeChanged`. `src/hooks/useUpdateLocation.js`.
2. Reducers read `params` and populate state in query/filters/view/trends.
   `src/reducers/query/querySlice.js`, `src/reducers/filters/filtersSlice.js`,
   `src/reducers/view/viewSlice.js`, `src/reducers/trends/trendsSlice.js`.
3. API params are created from state via `extractBasicParams`,
   `extractAggregationParams`, and `extractTrendsParams`.
   `src/api/params/params.js`.

## URL params that directly feed API params

These are accepted in the URL and end up in the API request (often with the
same name).

### Query + date filters (List/Map/Trends)

| URL query param | Redux field | API param | Notes |
| --- | --- | --- | --- |
| `searchText` | `query.searchText` | `search_term` | Renamed in `extractQueryParams`. `src/api/params/params.js`. |
| `searchField` | `query.searchField` | `field` | Renamed in `extractQueryParams`. |
| `date_received_min` | `query.date_received_min` | `date_received_min` | Same name. |
| `date_received_max` | `query.date_received_max` | `date_received_max` | Same name. |
| `company_received_min` | `query.company_received_min` | `company_received_min` | Same name. |
| `company_received_max` | `query.company_received_max` | `company_received_max` | Same name. |
| `size` | `query.size` | `size` | List queries. |
| `page` | `query.page` | `page` | Used for URL state; API uses `frm`. |
| `search_after` | `query.searchAfter` | `search_after` | Direct pass-through. |
| `sort` | `query.sort` | `sort` | List queries. |

### Filter params (List/Map/Trends)

Filter params are treated as arrays and passed directly to API with the same
name. The known filter keys are defined in `src/constants/index.js` and parsed
via `processUrlArrayParams` in `src/reducers/filters/filtersSlice.js`.

| URL query param | API param |
| --- | --- |
| `company` | `company` |
| `company_public_response` | `company_public_response` |
| `company_response` | `company_response` |
| `consumer_consent_provided` | `consumer_consent_provided` |
| `consumer_disputed` | `consumer_disputed` |
| `issue` | `issue` |
| `product` | `product` |
| `state` | `state` |
| `submitted_via` | `submitted_via` |
| `tags` | `tags` |
| `timely` | `timely` |
| `zip_code` | `zip_code` |
| `has_narrative` | `has_narrative` |

## URL params that affect API params indirectly

### Pagination (List)

* URL param `page` is stored in `query.page`, but API requests use `frm`
  computed from `page` and `size` (unless `query.from` is set).
  `src/api/params/params.js`.

### Trends

`extractTrendsParams` converts trends state into API parameters:
`src/api/params/params.js`.

| URL query param | Redux field | API param | Notes |
| --- | --- | --- | --- |
| `dateInterval` | `query.dateInterval` | `trend_interval` | Lowercased. |
| `lens` | `trends.lens` | `lens` | Lowercased, spaces -> underscores. |
| `subLens` | `trends.subLens` | `sub_lens` | Lowercased, spaces/dashes -> underscores. |
| `trend_depth` | `trends.trendDepth` | `trend_depth` | Same name. |
| `focus` | `trends.focus` | `focus` | Same name. |
| `chartType` | `trends.chartType` | `chartType` | Included in API params for trends. |

## URL params used for UI only (not sent to API)

These appear in the URL but do not map to API params directly.

* `tab` (List/Map/Trends), `isPrintMode`, `expandedRows`, `tour`, `debug`.
  `src/reducers/view/viewSlice.js`, `src/middleware/synchUrl/synchUrl.js`.
* `dataNormalization`, `enablePer1000`, `mapWarningEnabled` are filters state
  but excluded from API params in `extractAggregationParams` and
  `extractBasicParams`. `src/api/params/params.js`.

## Additional mapping helpers

* `stateToQS` in `src/reducers/query/querySlice.js` includes an explicit
  internal-to-API field map:
  * `searchText` -> `search_term`
  * `searchField` -> `field`
  * `searchAfter` -> `search_after`
  * `from` -> `frm`

```python
query_to_api_mappings = {
    "api_to_query": {
        "search_term": "searchText",  # src/api/params/params.js
        "field": "searchField",  # src/api/params/params.js
        "search_after": "search_after",  # src/api/params/params.js
        "size": "size",  # src/api/params/params.js
        "sort": "sort",  # src/api/params/params.js
        "date_received_min": "date_received_min",  # src/api/params/params.js
        "date_received_max": "date_received_max",  # src/api/params/params.js
        "company_received_min": "company_received_min",  # src/api/params/params.js
        "company_received_max": "company_received_max",  # src/api/params/params.js
        "company": "company",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "company_public_response": "company_public_response",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "company_response": "company_response",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "consumer_consent_provided": "consumer_consent_provided",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "consumer_disputed": "consumer_disputed",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "issue": "issue",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "product": "product",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "state": "state",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "submitted_via": "submitted_via",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "tags": "tags",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "timely": "timely",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "zip_code": "zip_code",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "has_narrative": "has_narrative",  # src/constants/index.js + src/reducers/filters/filtersSlice.js
        "trend_interval": "dateInterval",  # src/api/params/params.js
        "lens": "lens",  # src/api/params/params.js
        "sub_lens": "subLens",  # src/api/params/params.js
        "trend_depth": "trend_depth",  # src/api/params/params.js
        "focus": "focus",  # src/api/params/params.js
        "chartType": "chartType",  # src/api/params/params.js (not in swagger-config.yml)
        "format": "format",  # src/components/Dialogs/DataExport/dataExportUtils.js
        "no_aggs": "no_aggs",  # src/api/params/params.js
        "frm": "page",  # src/api/params/params.js (derived from page/size)
    },
}
```

## Notes for a deeplink URL generation engine (test agent)

Audience: a coding agent writing tests for a deeplink URL generator. The engine
will take an API query, generate a deeplink URL, and then curl the URL to check
HTML results against the API results. This section summarizes what the agent
needs without requiring repository access.

### What a deeplink URL looks like

* The explorer uses the current page URL plus query parameters for state.
* Query params are parsed on page load and converted to API params via Redux.
* The minimum requirement for a deeplink to function is that its query params
  map into the API request params used by the UI.

### URL params that map to API params (core set)

These are the most reliable keys to use when generating a deeplink from an API
query. Values are passed through unless otherwise noted.

* `search_term` <- URL `searchText`
* `field` <- URL `searchField`
* `date_received_min`
* `date_received_max`
* `company_received_min`
* `company_received_max`
* `company`
* `company_public_response`
* `company_response`
* `consumer_consent_provided`
* `consumer_disputed`
* `issue`
* `product`
* `state`
* `submitted_via`
* `tags`
* `timely`
* `zip_code`
* `has_narrative`
* `size`
* `sort`
* `search_after`
* `trend_interval` <- URL `dateInterval`
* `lens`
* `sub_lens` <- URL `subLens`
* `trend_depth`
* `focus`

### URL params that do NOT map to API params

These are UI-only and should be ignored by your engine when translating API
queries to URLs.

* `tab`, `isPrintMode`, `expandedRows`, `tour`, `debug`
* `dateRange` (used to infer dates; not sent directly)
* `dateInterval` (only used to set `trend_interval`)

### Pagination rules (List)

* The API uses `frm` and `search_after` for pagination.
* The URL uses `page` and `size`; the UI computes `frm` as:
  * `frm = (page - 1) * size`
* If you only have API params, you can invert this by:
  * `page = (frm / size) + 1` if `size` is known.

### Trends rules

* `lens` is lowercased and underscores replace spaces.
* `sub_lens` is lowercased and underscores replace spaces/dashes.
* `trend_interval` is lowercased.

### Constraints and validations

* `size`, `page`, `trend_depth` are parsed as integers.
* If `date_received_min`/`date_received_max` are invalid, route updates are
  ignored (deeplink effectively no-ops).
* `search_after` is stripped from URL-derived route params before equality
  comparison (route normalization removes it).

### API endpoints and allowed params

The Swagger file (`swagger-config.yml`) defines these param lists. Use them to
validate you are producing an API query that the UI can represent.

* `/` (search root): `search_term`, `field`, `frm`, `size`, `sort`, `format`,
  `no_aggs`, `no_highlight`, `company`, `company_public_response`,
  `company_received_max`, `company_received_min`, `company_response`,
  `consumer_consent_provided`, `consumer_disputed`, `date_received_max`,
  `date_received_min`, `has_narrative`, `issue`, `product`, `search_after`,
  `state`, `submitted_via`, `tags`, `timely`, `zip_code`
* `/geo/states`: same as above minus `frm`, `size`, `sort`, `format`,
  `no_aggs`, `no_highlight`, `search_after`
* `/trends`: `search_term`, `field`, `company`, `company_public_response`,
  `company_received_max`, `company_received_min`, `company_response`,
  `consumer_consent_provided`, `consumer_disputed`, `date_received_max`,
  `date_received_min`, `focus`, `has_narrative`, `issue`, `lens`, `product`,
  `state`, `submitted_via`, `sub_lens`, `sub_lens_depth`, `tags`, `timely`,
  `trend_depth`, `trend_interval`, `zip_code`

### Practical mapping guidance for tests

* When given API params, map to URL params using:
  * `search_term` -> `searchText`
  * `field` -> `searchField`
  * `frm` -> `page` (derived; see pagination)
  * `sub_lens` -> `subLens`
  * `trend_interval` -> `dateInterval`
* Keep filter params identical in name and value.
* If you include `format` for exports, the UI sets `no_aggs=true` and removes
  `searchAfter`/`from` from the URL when generating export links.

### One-way mappings (not reliably reversible)

* `dateRange` -> `date_received_min`/`date_received_max` depends on the
  backend’s “last indexed” date; you can’t always infer the original
  `dateRange` from dates alone.
* `search_after` is derived from API response breakpoints; the URL can carry it
  forward, but you can’t reconstruct it from other params.

### Gotchas

* Array filters: the UI parses array params; a single string becomes a 1-item
  array. Ensure your URL generator handles both repeated keys and singletons.
* `search_after`: accepted in URL and sent to the API, but stripped from route
  normalization comparisons; avoid relying on it for equality checks.
* Date validation: invalid `date_received_*` or `company_received_*` causes the
  route update to be ignored.
* Trends casing: `dateInterval` is converted to lowercase `trend_interval`
  before calling the API.
* Dotted names: there are no query params with dots. Dotted keys like
  `field.raw` appear in response schemas, not as query params.
* Dotted mapping values (e.g., `query.dateInterval`) indicate Redux state paths,
  not URL or API keys; the engine can ignore them.

### Known gaps / ambiguity

* `chartType` is included in trends API params in UI code but is not listed in
  `swagger-config.yml`. Treat as UI-driven or ignore for API parity checks.

### Example API -> deeplink URL conversions

These are illustrative and use the live CFPB base URL.

1. Simple search (list)

API params:

```json
{
  "search_term": "mortgage",
  "field": "all",
  "size": 25,
  "sort": "created_date_desc",
  "frm": 0
}
```

Deeplink URL:

```
https://www.consumerfinance.gov/data-research/consumer-complaints/search/?searchText=mortgage&searchField=all&size=25&sort=created_date_desc&page=1
```

2. Filtered list with pagination

API params:

```json
{
  "product": ["Credit card"],
  "state": ["CA"],
  "date_received_min": "2023-01-01",
  "date_received_max": "2023-12-31",
  "size": 50,
  "frm": 50
}
```

Deeplink URL:

```
https://www.consumerfinance.gov/data-research/consumer-complaints/search/?product=Credit%20card&state=CA&date_received_min=2023-01-01&date_received_max=2023-12-31&size=50&page=2
```

3. Trends query

API params:

```json
{
  "lens": "product",
  "trend_interval": "month",
  "trend_depth": 5,
  "date_received_min": "2022-01-01",
  "date_received_max": "2022-12-31",
  "product": ["Mortgage"]
}
```

Deeplink URL:

```
https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=Trends&lens=product&dateInterval=Month&trend_depth=5&date_received_min=2022-01-01&date_received_max=2022-12-31&product=Mortgage
```

4. Trends focus with sub-lens

API params:

```json
{
  "lens": "product",
  "sub_lens": "sub_product",
  "focus": "Mortgage",
  "trend_interval": "week",
  "trend_depth": 10
}
```

Deeplink URL:

```
https://www.consumerfinance.gov/data-research/consumer-complaints/search/?tab=Trends&lens=product&subLens=sub_product&focus=Mortgage&dateInterval=Week&trend_depth=10
```

5. Actual deeplink (provided)

Deeplink URL:

```
https://www.consumerfinance.gov/data-research/consumer-complaints/search/?chartType=line&dateInterval=Month&dateRange=3y&date_received_max=2025-12-20&date_received_min=2022-12-20&lens=Product&searchField=all&subLens=sub_product&tab=Trends
```

API params (derived):

```json
{
  "lens": "product",
  "sub_lens": "sub_product",
  "trend_interval": "month",
  "date_received_min": "2022-12-20",
  "date_received_max": "2025-12-20",
  "field": "all"
}
```
