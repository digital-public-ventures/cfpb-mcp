Below is a **README written for a custom coding agent** that will implement this in two phases. It assumes the agent has access to (and should read) the existing `server.py` and current `README.md`, and it encodes the architectural intent that already exists in those files rather than restating generic MCP docs.

***

# CFPB Complaints MCP

## Phased Packaging: Desktop `.mcpb` Shim → Claude Custom Connector

### Audience

This README is written for an **autonomous coding agent** responsible for packaging and deploying an existing **remote MCP server** in two stages:

1. **Phase 1:** A Claude Desktop Extension (`.mcpb`) that runs a *local MCP shim* and proxies all traffic to the existing remote server.
2. **Phase 2:** A **Claude Custom Connector** that allows Claude (Desktop, Web, Mobile) to connect *directly* to the remote MCP server without a local shim.

The agent should treat the current Python server as **authoritative** and avoid changing its semantics unless explicitly instructed.

***

## Canonical Source of Truth (Read First)

Before implementing anything, the agent **must read**:

* `server.py`
* the existing `README.md`

Key facts established there (do not re-invent):

* The MCP server is implemented in **Python (FastAPI + FastMCP)**.
* MCP is exposed over **SSE** at:

  ```
  /mcp/sse
  ```

  via:

  ```python
  app.mount("/mcp", server.sse_app())
  ```
* The server already supports:

  * Tool definitions
  * Tool invocation
  * Proper MCP SSE semantics
* The current development/testing flow uses:

  ```json
  {
    "cfpb-complaints": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://<server>/mcp/sse",
        "--allow-http",
        "--transport",
        "sse-only"
      ]
    }
  }
  ```

This configuration **works** and should be treated as the reference behavior.

***

## High-Level Architecture

```
Claude
  |
  |  (Phase 1: stdio MCP)
  v
Local MCP Shim (.mcpb)
  |
  |  (SSE MCP)
  v
Remote MCP Server (existing FastAPI app)
```

```
Claude
  |
  |  (Phase 2: Remote MCP Connector)
  v
Remote MCP Server (same /mcp/sse endpoint)
```

The remote server **does not change** between phases.

***

## Phase 1: Claude Desktop Extension (`.mcpb`)

### Goal

Package the existing remote MCP server as a **Claude Desktop Extension** by shipping a *local MCP server* that transparently proxies all MCP traffic to:

```
https://<DEPLOYED_SERVER>/mcp/sse
```

### Constraints

* Claude Desktop extensions **must run locally**
* They communicate with Claude over **stdio MCP**
* They may call arbitrary remote services
* The local component should be as thin as possible

### Implementation Strategy (Required)

**Do NOT re-implement MCP logic in Python locally.**
Instead, create a **Node-based MCP shim** that delegates to the remote server.

Preferred approaches (in order):

1. **Wrap `mcp-remote`**

   * This exactly matches the known-working setup.
   * The extension’s command should effectively be:

     ```
     npx mcp-remote <REMOTE_URL>/mcp/sse --transport sse-only
     ```
   * Node is preferred because Claude Desktop bundles a Node runtime.

2. (Optional later) Replace `mcp-remote` with a minimal custom proxy

   * Only if needed for auth, headers, or policy enforcement.

### Required Deliverables (Phase 1)

* `manifest.json`

  * Declares:

    * name, description, version
    * command entrypoint
    * optional user-configurable settings
* `index.js` (or equivalent)

  * Launches the MCP proxy
  * Pipes stdio ↔ remote SSE
* `.mcpb` bundle

  * Installable by double-click in Claude Desktop

### Configuration Requirements

The extension **must support configuration** for:

* `REMOTE_MCP_URL`

  * Default: the deployed server URL
* `ALLOW_HTTP` (boolean)

  * Needed for local/dev environments
* (Future-proof) `API_KEY` or OAuth token placeholder

These should surface in Claude’s extension UI if supported.

### Non-Goals for Phase 1

* No auth enforcement beyond pass-through
* No tool rewriting
* No schema mutation
* No server-side changes unless required for correctness

The shim is intentionally dumb.

***

## Phase 2: Claude Custom Connector (Remote MCP)

### Goal

Allow Claude (Desktop, Web, Mobile) to connect **directly** to the remote MCP server without a local extension.

This uses Anthropic’s **Custom Connector / Remote MCP** capability.

### Preconditions

Before Phase 2 starts, confirm:

* `/mcp/sse` is publicly reachable over HTTPS
* The server:

  * Handles multiple concurrent clients
  * Enforces rate limits
  * Can authenticate users or orgs (if required)

### Required Server Capabilities

The agent should verify (and implement if missing):

1. **Authentication**

   * API key header **or**
   * OAuth 2.0 (preferred long-term)
2. **Tenant isolation**

   * Tool calls must be attributable to a user/org
3. **Audit logging**

   * Tool name
   * Arguments (redacted as needed)
   * Timestamp
4. **Stability**

   * Deterministic JSON outputs
   * Explicit error objects

### Connector Registration Artifacts

The agent will need to prepare:

* Connector metadata (name, description, icon)
* Auth configuration
* MCP endpoint URL:

  ```
  https://<server>/mcp/sse
  ```
* Tool discovery confirmation

No `.mcpb` is used in this phase.

***

## Critical Invariants (Do Not Break)

* `/mcp/sse` remains the canonical MCP endpoint
* Tool names and schemas must stay stable
* Existing Claude Desktop shim config must continue to work
* SSE transport remains supported (no WebSocket-only migration)

***

## Testing Matrix (Required)

### Phase 1

* Claude Desktop + `.mcpb`
* Tools list correctly
* Tools execute and return expected JSON
* Server logs show remote calls (not local execution)

### Phase 2

* Claude Desktop (via Connectors UI)
* Claude Web
* Claude Mobile (if enabled)
* Auth failures handled cleanly
* Multiple users do not leak data

***

## Design Philosophy (Important)

* **Remote-first:** all business logic lives on the server
* **Thin adapters:** desktop extension and connector do not encode policy
* **MCP-native:** no Claude-specific hacks in tool logic
* **Future-ready:** same server should work with OpenAI, Anthropic, or other MCP clients

***

## When to Ask for Clarification

The agent should pause and ask before:

* Changing tool schemas
* Adding write/mutation tools
* Introducing irreversible actions
* Implementing OAuth vs API keys
* Caching or summarization at the proxy layer

***

## Summary

* Phase 1 turns an existing working MCP SSE server into a **first-class Claude Desktop Extension**
* Phase 2 promotes the same server into a **direct Claude Custom Connector**
* The Python server is the product; everything else is packaging

If done correctly, **no Claude-specific logic ever enters `server.py`**—only standards-compliant MCP.

***

**End of instructions for the coding agent.**
