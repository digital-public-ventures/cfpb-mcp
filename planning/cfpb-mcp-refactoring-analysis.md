# CFPB MCP Server Refactoring Analysis

## Executive Summary

Your power user correctly identified the core problem: **the server assumes every call is the final call**. The current architecture passes CFPB API responses through with minimal transformation, creating 50KB+ responses for simple questions.

The proposed refactoring guide is thorough but ambitious—it suggests both slimming existing tools AND adding 7 new purpose-built tools. This tension needs resolution. Below I analyze the trade-offs and propose a path that prioritizes simplification.

---

## The Constraint You're Working Within

Your server is a thin wrapper around the CFPB public API. You can't change what the upstream API returns—you can only:

1. **Pass different parameters** to the API (e.g., `no_aggs=true`, `size=0`)
2. **Post-process the response** before returning it to the agent

Looking at your code, `search_logic` currently hardcodes `no_aggs: False`:

```python
params.update({
    'size': size,
    'frm': from_index,
    'sort': sort,
    'search_after': search_after,
    'no_highlight': no_highlight,
    'no_aggs': False,  # ← This is the problem
})
```

The upstream API likely supports `no_aggs: true`. This is your biggest lever.

---

## Option Analysis

### Path A: Minimal Changes (Recommended Starting Point)

**Philosophy**: Change defaults and add a few parameters to existing tools. No new tools.

| Change | Effort | Token Reduction | Risk |
|--------|--------|-----------------|------|
| Set `no_aggs=True` by default, add `include_aggregations` param | Low | 30-40KB per search | Low |
| Reduce default `size` from 10 to 3 | Trivial | ~50% of hit payload | Low |
| Truncate narratives to 500 chars in response | Low | 80-90% of narrative tokens | Low |
| Add `count_only` mode to search | Low | 95%+ for existence checks | Low |

**Implementation sketch:**

```python
async def search_complaints(
    # ... existing params ...
    include_aggregations: bool = False,  # NEW: default OFF
    narrative_length: int = 500,         # NEW: -1 for full
    count_only: bool = False,            # NEW: just return count
    size: int = 3,                        # CHANGED: was 10
):
    if count_only:
        # size=0 query, return just total
        data = await search_logic(size=0, no_aggs=True, ...)
        return {"count": data["hits"]["total"], "citations": [...]}
    
    data = await search_logic(
        size=size,
        no_aggs=not include_aggregations,
        ...
    )
    
    # Post-process: truncate narratives
    if narrative_length >= 0:
        for hit in data.get("hits", {}).get("hits", []):
            narrative = hit.get("_source", {}).get("complaint_what_happened", "")
            if len(narrative) > narrative_length:
                hit["_source"]["complaint_what_happened"] = narrative[:narrative_length] + "..."
                hit["_source"]["narrative_truncated"] = True
    
    return {"data": data, "citations": [...]}
```

**Pros:**
- Minimal code change (~50 lines)
- No new tools for agents to discover
- Backward compatible (agents that want full data can request it)
- Easy to test and reason about

**Cons:**
- Agents must learn the new parameters
- Doesn't provide workflow-specific conveniences

---

### Path B: Add One Strategic Tool

**Philosophy**: Path A + add exactly ONE new tool that provides maximum leverage.

The most universally useful addition is `count_complaints`:

```python
@server.tool()
async def count_complaints(
    # Same filter params as search_complaints, but no size/sort/pagination
    search_term: str | None = None,
    company: list[str] | None = None,
    product: list[str] | None = None,
    # ... other filters ...
) -> dict:
    """
    Get complaint count matching filters. Fastest possible query.
    
    Use for: existence checks, sizing a result set before fetching,
    comparing volumes across categories.
    """
    data = await search_logic(size=0, no_aggs=True, ...)
    return {
        "count": data["hits"]["total"],
        "search_url": build_cfpb_ui_url(...)
    }
```

**Why this one tool?**

1. **Universal utility**: Every workflow starts with "how many?" 
2. **Maximum token savings**: 50KB → 200 bytes (99.6% reduction)
3. **Zero learning curve**: Agents understand "count" intuitively
4. **Clear separation**: Answers a distinct question that search doesn't do well

**What I'd defer:**

| Proposed Tool | Why Defer |
|---------------|-----------|
| `find_constituent_stories` | Workflow-specific; agents can compose this from filters |
| `compare_time_periods` | Complex logic that may not match real usage patterns |
| `detect_emerging_issues` | Already covered by `rank_company_spikes` and `rank_group_spikes` |
| `get_market_snapshot` | Requires maintaining market definitions; high maintenance |
| `get_trend_summary` | `get_overall_trend_signals` already does this |

---

### Path C: Response Transformation Layer

**Philosophy**: Instead of adding tools, add a response transformation layer.

```python
ResponseFormat = Literal["full", "summary", "compact"]

def transform_response(data: dict, format: ResponseFormat) -> dict:
    if format == "full":
        return data
    
    if format == "compact":
        # Strip aggregations, truncate narratives, flatten structure
        return {
            "total": data["hits"]["total"],
            "hits": [
                {
                    "id": h["_source"]["complaint_id"],
                    "company": h["_source"]["company"],
                    "product": h["_source"]["product"],
                    "date": h["_source"]["date_received"],
                    "narrative_preview": h["_source"].get("complaint_what_happened", "")[:200]
                }
                for h in data.get("hits", {}).get("hits", [])
            ]
        }
    
    if format == "summary":
        # Return structured summary with top-N aggregations
        ...
```

**Apply to all tools:**

```python
@server.tool()
async def search_complaints(
    # ... existing params ...
    format: ResponseFormat = "compact",  # NEW
):
    data = await search_logic(...)
    return transform_response(data, format)
```

**Pros:**
- Single abstraction applies everywhere
- Agents get consistent interface across tools
- Easy to add new formats later

**Cons:**
- More code to maintain than Path A
- Format semantics need documentation
- May not match agent mental models

---

## My Recommendation: Path A + One Tool

Start with the minimal changes. They're low-risk, high-impact, and reversible.

### Phase 1 (Do This Week)

1. **Flip the aggregation default**
   - Change `no_aggs: False` → `no_aggs: True` in `search_logic`
   - Add `include_aggregations: bool = False` parameter to `search_complaints`

2. **Reduce default size**
   - Change `size: int = 10` → `size: int = 3`

3. **Add narrative truncation**
   - Add `narrative_length: int = 500` parameter
   - Post-process hits to truncate

4. **Add `count_only` mode**
   - Add `count_only: bool = False` to `search_complaints`
   - When true, return `{"count": N, "search_url": ...}`

**Expected impact**: 70-90% token reduction for typical queries.

### Phase 2 (After Observing Usage)

5. **Add `count_complaints` as a dedicated tool** (if agents aren't using `count_only` mode)

6. **Consider `compact` parameter** if agents need structured summaries frequently

### What I'd Explicitly NOT Do

- **Don't add workflow-specific tools yet.** Wait to see how agents actually use the improved base tools. You might find agents compose workflows just fine with count + search + get_document.

- **Don't restructure the trends API.** The nesting is annoying but not catastrophic. The aggregation fix in search will have much higher impact.

- **Don't add market definitions.** They require ongoing maintenance and will drift from reality.

---

## Quick Wins From the Proposal Worth Adopting

These require minimal thought and have no downsides:

| Quick Win | Change |
|-----------|--------|
| Move citations to top of response | Reorder dict keys in return |
| Remove redundant query body echo | `del response["aggregations"]["dateRangeBuckets"]["body"]` |
| Limit aggregation buckets | Add `size: 10` to ES agg queries |
| Flatten aggregation structure | Transform `{company: {company: {buckets}}}` → `{company: {buckets}}` |

---

## Implementation Priority Matrix

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 🔴 P0 | Set `no_aggs=True` default + add `include_aggregations` param | 2 hrs | Huge |
| 🔴 P0 | Add narrative truncation (500 chars default) | 1 hr | Large |
| 🟡 P1 | Reduce default size to 3 | 5 min | Medium |
| 🟡 P1 | Add `count_only` mode to search | 1 hr | Large |
| 🟢 P2 | Flatten aggregation structure in response | 2 hrs | Medium |
| 🟢 P2 | Move citations to top of response | 30 min | Small |
| 🔵 P3 | Add dedicated `count_complaints` tool | 2 hrs | Medium |

---

## Code Smell Worth Addressing

Your tools have massive parameter duplication. Every tool repeats the same 15+ filter parameters. Consider extracting a shared filter type:

```python
from pydantic import BaseModel

class ComplaintFilters(BaseModel):
    search_term: str | None = None
    company: list[str] | None = None
    product: list[str] | None = None
    issue: list[str] | None = None
    state: list[str] | None = None
    # ... etc

@server.tool()
async def search_complaints(
    filters: ComplaintFilters,
    size: int = 3,
    include_aggregations: bool = False,
    narrative_length: int = 500,
):
    ...
```

This won't reduce tokens but will make the codebase much more maintainable. Whether MCP/FastMCP supports this cleanly is worth checking.

---

## Summary

The power user's pain is real: you're returning 50KB when 500 bytes would do. But the solution isn't more tools—it's smarter defaults.

**Do first:**
1. `no_aggs=True` by default
2. Truncate narratives by default
3. Reduce hit count by default

**Do second:**
1. Add `count_only` mode
2. Consider `count_complaints` tool

**Defer:**
1. Workflow-specific tools
2. Response format abstraction
3. Market snapshot definitions

The goal is a server that returns the minimum viable data for each query type, with explicit opt-in for more detail. Start sparse, add on request.
