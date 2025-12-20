# MCP OAuth Best Practices for Claude Custom Connectors

*Last updated: December 19, 2025*

## Situation

You have an existing HTTPS server exposing an MCP/SSE endpoint. Goal: implement OAuth that works today on SSE, with a clear path to Streamable HTTP when you're ready.

This doc is written to support **Claude Custom Connectors** specifically, and to stay compatible with FastMCP's recommended OAuth patterns.

***

## Current State: What Claude Supports

### Transport

Claude supports both **SSE** and **Streamable HTTP** remote servers. However, SSE may be deprecated in the coming months. The ecosystem standard is now:

* **stdio** for local/desktop
* **Streamable HTTP** for remote/web

**Recommendation:** Get OAuth working on SSE first (validates your auth implementation), then add Streamable HTTP as a second endpoint using the same OAuth setup.

### Auth Specs

Claude supports:

* **3/26 auth spec** (original)
* **6/18 auth spec** (current standard, as of July 2025)
* **Dynamic Client Registration (DCR)** per RFC 7591
* **Static client credentials** - users can specify custom client ID/secret when adding a connector that doesn't support DCR

### OAuth Callback URLs

Allowlist both:

```
https://claude.ai/api/mcp/auth_callback
https://claude.com/api/mcp/auth_callback
```

Claude's OAuth client name is `Claude`.

### The 6/18 Spec Key Requirements

The June 2025 revision established MCP servers as **OAuth Resource Servers** (not authorization servers). Your MCP server validates tokens from an external IdP.

**Required endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `/.well-known/oauth-protected-resource` | Advertises your authorization server (RFC 9728) |
| Authorization server's `/.well-known/oauth-authorization-server` | OAuth metadata discovery (RFC 8414) |

***

## Architecture: Dual Transport with Shared OAuth

You can serve both SSE and Streamable HTTP from the same server, sharing all OAuth infrastructure.

```
https://your-server.example.com/
├── .well-known/
│   └── oauth-protected-resource    ← Shared, points to your IdP
├── /mcp                            ← Streamable HTTP (POST + GET for SSE upgrade)
└── /mcp/sse                        ← Legacy SSE endpoint

Note: In this repository today, the MCP endpoint is exposed at `/mcp/sse` and there is also a companion messages endpoint (`/mcp/messages`) for the legacy SSE transport.

### FastMCP vs “pure resource server” (important)

There are two viable implementation styles:

1) **Pure token validation (resource-server style):** your MCP server validates bearer tokens issued by an external authorization server (Auth0/Keycloak/Azure AD/etc). In this model, your server must still publish the protected-resource metadata at `/.well-known/oauth-protected-resource` (RFC 9728), which points clients at the external authorization server metadata (RFC 8414).

2) **FastMCP OAuth Proxy (recommended when your upstream IdP does not support DCR):** FastMCP's OAuth Proxy pattern presents a DCR-compatible interface to MCP clients and can issue its own tokens while brokering to an upstream provider. In this model, the “authorization server” the client talks to is effectively your server (the proxy), even though it may federate to an upstream provider.

Claude supports both DCR and static client credentials. For early testing, static client credentials are typically the simplest path regardless of which model you choose.
```

### What's Shared vs. Separate

| Component | Shared? |
|-----------|---------|
| Authorization Server (IdP) | ✅ Yes |
| `/.well-known/oauth-protected-resource` | ✅ Yes |
| Token validation logic | ✅ Yes |
| Client registrations (DCR or static) | ✅ Yes |
| MCP tool implementations | ✅ Yes |
| Transport handling code | ❌ No (separate) |

OAuth operates above the transport layer - bearer tokens work identically whether delivered over SSE or Streamable HTTP.

***

## Selective Authentication Pattern

**Critical:** Claude expects certain MCP methods to work *without* authentication for protocol bootstrapping.

### Unauthenticated (allow without token)

* `/.well-known/oauth-protected-resource` — must be public for discovery
* For legacy SSE servers mounted at `/mcp/sse`:
  * `GET /mcp/sse` — establish the SSE connection
  * `POST /mcp/messages` with `initialize` and `notifications/initialized`
* For Streamable HTTP servers mounted at `/mcp`:
  * `POST /mcp` with `initialize` and `notifications/initialized`

### Authenticated (require valid bearer token)

* `tools/list` — Full validation
* `tools/call` — Each tool execution

Practical guidance: implement selective auth at the MCP message-method level (initialize + initialized allowed) rather than trying to special-case only HTTP verbs. This avoids brittle behavior across transports.

***

## Protected Resource Metadata

Your server must expose `/.well-known/oauth-protected-resource`:

```json
{
  "resource": "https://your-server.example.com",
  "authorization_servers": ["https://your-idp.example.com"],
  "scopes_supported": ["mcp:read", "mcp:tools"],
  "bearer_methods_supported": ["header"],
  "resource_documentation": "https://your-server.example.com/docs",
  "mcp_protocol_version": "2025-06-18",
  "resource_type": "mcp-server"
}

If you use an OAuth Proxy pattern where your server effectively becomes the OAuth surface for clients, `authorization_servers` may point to your server's issuer URL instead of the upstream IdP.
```

***

## Auth Strategy Options

### Option A: Full DCR with External IdP (Recommended for Production)

* Use Auth0, Keycloak, or Azure AD as your authorization server
* Your MCP server only validates tokens (stateless)
* Enables "plug and play" - any MCP client can auto-register

**Note:** DCR requires your IdP to allow anonymous client registration, which is disabled by default in most IdPs. You'll need to explicitly enable it.

### Option B: Static Client Credentials (Simpler for Testing)

* Pre-register "Claude" as a client in your IdP
* Users enter the client ID when adding the connector in Claude settings
* Skips DCR complexity initially

**Recommendation:** Start with Option B to validate the flow, then add DCR support.

### Option C: OAuth Proxy (FastMCP pattern for non-DCR providers)

If you pick an IdP that does not support Dynamic Client Registration (GitHub/Google/Azure/most enterprise providers), prefer an OAuth Proxy approach (as described in FastMCP's auth docs). This avoids forcing your IdP to allow anonymous DCR.

***

## Implementation Phases

### Phase 1: Add OAuth to Existing SSE Endpoint

1. Choose your IdP (Auth0 free tier or Keycloak recommended)
2. Create a client registration for Claude with:
   * Redirect URIs: `https://claude.ai/api/mcp/auth_callback`, `https://claude.com/api/mcp/auth_callback`
   * Grant type: Authorization Code with PKCE
   * Scopes: Define your `mcp:*` scopes
3. Implement `/.well-known/oauth-protected-resource` endpoint
4. Add token validation middleware to your SSE endpoint
5. Implement selective authentication (allow init without token)

If you choose an OAuth Proxy approach, replace step (4) with integrating the proxy's validation and discovery endpoints rather than custom middleware.

### Phase 2: Test with Claude

1. Use MCP Inspector first:
   ```bash
   npx @modelcontextprotocol/inspector
   ```
   * Select "SSE" transport
   * Enter your server URL
   * Click "Open Auth Settings" → "Quick OAuth Flow"
   * Verify auth completes successfully

2. Add connector in Claude:
   * Go to Settings → Connectors → Add custom connector
   * Enter your MCP server URL
   * If not using DCR: Click "Advanced settings" and enter your client ID/secret
   * Click "Connect" and complete OAuth flow

### Phase 3: Add Streamable HTTP Endpoint

1. Add `/mcp` endpoint supporting:
   * `POST` for JSON-RPC requests
   * `GET` for server-initiated SSE streams (optional)
2. Apply same token validation middleware
3. Share session state store if maintaining sessions

### Phase 4: Migration

When ready to switch (or when Claude deprecates SSE):

1. Update your connector URL from `/mcp/sse` to `/mcp`
2. No re-authentication needed - same tokens work

***

## Session State Considerations

If maintaining sessions across requests:

* Both transports may hit the same session store
* SSE connections are long-lived; Streamable HTTP connections may be shorter
* Consider Redis or similar for shared state if running multiple instances
* In-memory state works for single-instance deployments but doesn't scale horizontally

***

## Key Resources

### Official Documentation

* [MCP Authorization Spec (6/18)](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
* [Claude Custom Connectors Guide](https://support.claude.com/en/articles/11503834-building-custom-connectors-via-remote-mcp-servers)
* [MCP Roadmap & Changelog](https://modelcontextprotocol.io/development/roadmap)

### SDK References

* [TypeScript SDK Auth](https://github.com/modelcontextprotocol/typescript-sdk/tree/main/src/server/auth)
* [Python SDK Examples](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples/servers)

### Libraries & Tools

* [MCP-Auth](https://mcp-auth.dev/docs) — Handles RFC 9728 metadata endpoints
* [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) — Test and debug your server
* [Cloudflare MCP Hosting](https://developers.cloudflare.com/agents/guides/remote-mcp-server/) — Managed hosting with OAuth

### FastMCP references (implementation-oriented)

* FastMCP auth overview: choose between TokenVerifier / Remote OAuth / OAuth Proxy depending on IdP capabilities
* Pay attention to well-known route mounting requirements if the MCP app is not at the domain root (FastMCP calls this out explicitly)

### Tutorials

* [Christian Posta's MCP Authorization Series](https://blog.christianposta.com/understanding-mcp-authorization-with-dynamic-client-registration/) — Excellent step-by-step walkthrough
* [Auth0 MCP Spec Updates Guide](https://auth0.com/blog/mcp-specs-update-all-about-auth/)
* [George Vetticaden's Missing MCP Playbook](https://medium.com/@george.vetticaden/the-missing-mcp-playbook-deploying-custom-agents-on-claude-ai-and-claude-mobile-05274f60a970)

***

## Quick Reference: Claude IP Addresses

If allowlisting, see [Anthropic's IP documentation](https://docs.anthropic.com/en/api/ip-addresses#ipv4-2) for current inbound/outbound IPs used for MCP connections.

***

## Checklist

* \[ ] IdP selected and configured (Auth0/Keycloak/Azure AD)
* \[ ] Client registered with Claude callback URLs
* \[ ] `/.well-known/oauth-protected-resource` endpoint implemented
* \[ ] Token validation middleware added
* \[ ] Selective auth pattern implemented (init without token)
* \[ ] Tested with MCP Inspector
* \[ ] Tested with Claude custom connector
* \[ ] (Optional) Streamable HTTP endpoint added
* \[ ] (Optional) DCR enabled for plug-and-play clients
