# CFPB MCP Worker (TypeScript)

This is a TypeScript Cloudflare Worker port of the CFPB MCP server. It preserves
the Streamable HTTP MCP interface and exposes the same tool surface as the
Python implementation.

## Structure

```
src/
  index.ts            Worker entrypoint (auth/rate limit + MCP)
  tools/
    definitions.ts    Zod schemas and tool definitions
    handlers.ts       Tool handlers + citations logic
  utils/
    api.ts            CFPB API client + param normalization
    deeplink.ts       CFPB UI deeplink utilities
    math.ts           Trend stats and spike detection helpers
    security.ts       API key auth + rate limiting
```

## Local Dev

```
npm install
npm run dev
```

## Notes

- Streamable HTTP only: POST to `/mcp`.
- Rate limiting is in-memory and per isolate.
- API keys read from `CFPB_MCP_API_KEYS` (comma-separated).
