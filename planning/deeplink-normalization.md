## Goal

Centralize complaint deeplink enrichment so any tool that returns CFPB
complaint hits automatically includes `complaint_deeplink` without
duplicating logic in handlers.

## Current state

- `ts-mcp/src/tools/handlers.ts` decorates `search_complaints` and
  `get_complaint_document` responses by walking `hits.hits`.
- `ts-mcp/src/utils/deeplink.ts` exposes `appendComplaintDeeplinks`.
- The decoration logic lives in handlers, so any new tool must remember to call
  it.

## Proposed direction (more elegant)

### Option A: API-layer normalization (preferred)

Add a response-normalizer in `ts-mcp/src/utils/api.ts`:

- `normalizeComplaintPayload(payload: unknown): unknown`
  - If payload has `hits.hits`, decorate `_source` (or the hit itself) with
    `complaint_deeplink`.
  - Return payload unchanged if shape doesn't match.

Update `searchLogic` and `documentLogic` to call the normalizer before
returning:

- `return normalizeComplaintPayload(fetchJson(...))`

Pros:
- One place for complaint link enrichment.
- All tools that use these helpers inherit it.
- Keeps handler surface minimal.

Cons:
- Assumes complaint payloads always travel through `searchLogic` or
  `documentLogic`.

### Option B: Tool response wrapper

Wrap tool results just before returning (a single wrapper used by all handlers):

- `wrapToolResponse(payload)` in `ts-mcp/src/tools/handlers.ts`
- Applies `normalizeComplaintPayload` and `withContent`

Pros:
- Single step for both content and deeplinks.
- No changes needed in `api.ts`.

Cons:
- Handlers must all use the wrapper; potential footgun.

### Option C: MCP transport middleware

Normalize in the MCP transport layer (post-handler).

Pros:
- Transport-agnostic behavior for tool responses.

Cons:
- Harder to keep type-aware; applies to all responses, even non-complaint.

## Recommendation

Option A + shared normalizer:

1) Add `normalizeComplaintPayload` in `ts-mcp/src/utils/api.ts` or a new
   `ts-mcp/src/utils/normalize.ts`.
2) Call it inside `searchLogic` and `documentLogic`.
3) Keep `appendComplaintDeeplinks` in `ts-mcp/src/utils/deeplink.ts` for reuse.
4) Remove per-handler decoration once coverage is in place.

## Validation

- Existing integration test `ts-mcp/tests/integration/test_complaint_deeplinks.test.ts`
  should still pass.
- Add a small unit test for `normalizeComplaintPayload` using a minimal
  `hits.hits` fixture.
