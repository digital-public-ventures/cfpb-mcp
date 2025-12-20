# Phase 1 Implementation Plan: CFPB MCP Desktop Extension

## Overview

Create a `.mcpb` Claude Desktop Extension that acts as a local MCP shim, proxying all traffic to the existing remote CFPB MCP server running on `http://localhost:8000/mcp/sse`.

## Implementation Strategy

**Approach**: Minimal Node.js wrapper around `npx mcp-remote`

* Leverages existing, working configuration
* No custom MCP protocol implementation needed
* Uses Claude Desktop's bundled Node.js runtime
* Minimal package size (no bundled dependencies)

## Directory Structure

```
extension/
├── manifest.json          # Extension metadata and configuration
├── server/
│   └── index.js          # MCP proxy entrypoint
├── package.json          # Node package definition (optional/minimal)
└── README.md             # Extension documentation
```

## File Specifications

### 1. `manifest.json`

**Purpose**: Declares extension metadata, configuration, and runtime requirements.

**Key fields**:

```json
{
  "manifest_version": "0.3",
  "name": "cfpb-complaints",
  "display_name": "CFPB Consumer Complaints",
  "version": "1.0.0",
  "description": "Access CFPB consumer complaint data and trend analysis",
  "long_description": "Search consumer complaints, analyze trends, get geographic aggregations, and detect complaint spikes from the Consumer Financial Protection Bureau database.",
  "author": {
    "name": "Digital Public Ventures",
    "url": "https://github.com/digital-public-ventures"
  },
  "repository": {
    "type": "git",
    "url": "https://github.com/digital-public-ventures/cfpb-mcp.git"
  },
  "server": {
    "type": "node",
    "entry_point": "server/index.js",
    "mcp_config": {
      "command": "node",
      "args": ["${__dirname}/server/index.js"],
      "env": {
        "REMOTE_MCP_URL": "${user_config.remote_url}"
      }
    }
  },
  "tools": [
    {
      "name": "search_complaints",
      "description": "Search consumer complaints with filters"
    },
    {
      "name": "list_complaint_trends",
      "description": "Get complaint volume trends over time"
    },
    {
      "name": "get_state_aggregations",
      "description": "Get complaint counts by state"
    },
    {
      "name": "get_complaint_document",
      "description": "Retrieve a specific complaint by ID"
    },
    {
      "name": "suggest_filter_values",
      "description": "Get autocomplete suggestions for filters"
    },
    {
      "name": "generate_cfpb_dashboard_url",
      "description": "Generate URLs to official CFPB dashboard"
    },
    {
      "name": "get_overall_trend_signals",
      "description": "Detect anomalies in overall complaint trends"
    },
    {
      "name": "rank_group_spikes",
      "description": "Find products/issues with unusual complaint spikes"
    },
    {
      "name": "rank_company_spikes",
      "description": "Find companies with unusual complaint spikes"
    }
  ],
  "keywords": ["cfpb", "complaints", "consumer-protection", "financial", "data-analysis", "trends"],
  "license": "MIT",
  "compatibility": {
    "claude_desktop": ">=0.10.0",
    "platforms": ["darwin", "win32", "linux"],
    "runtimes": {
      "node": ">=16.0.0"
    }
  },
  "user_config": {
    "remote_url": {
      "type": "string",
      "title": "Server URL",
      "description": "URL of the CFPB MCP server (including /mcp/sse path)",
      "default": "http://localhost:8000/mcp/sse",
      "required": true
    }
  }
}
```

**Rationale**:

* Static tool declarations for discoverability
* User-configurable URL for flexibility (dev → staging → prod)
* Minimal compatibility constraints (Node 16+, all platforms)

### 2. `server/index.js`

**Purpose**: Launch `mcp-remote` and proxy stdio ↔ remote SSE.

**Implementation**:

```javascript
#!/usr/bin/env node
/**
 * CFPB MCP Desktop Extension - Local Proxy
 * 
 * This is a thin wrapper that delegates all MCP protocol handling
 * to the remote CFPB server via mcp-remote.
 */

const { spawn } = require('child_process');
const path = require('path');

// Get remote URL from environment (set by Claude Desktop from user_config)
const remoteUrl = process.env.REMOTE_MCP_URL || 'http://localhost:8000/mcp/sse';

// Log to stderr (Claude reads stdout for MCP protocol)
console.error(`[CFPB MCP] Connecting to: ${remoteUrl}`);

// Launch mcp-remote with npx
const proxy = spawn('npx', [
  '-y',                    // Auto-install if needed
  'mcp-remote',
  remoteUrl,
  '--allow-http',          // Allow localhost HTTP for dev
  '--transport', 'sse-only'
], {
  stdio: ['inherit', 'inherit', 'inherit'],
  env: process.env
});

// Forward exit code
proxy.on('exit', (code) => {
  console.error(`[CFPB MCP] Proxy exited with code ${code}`);
  process.exit(code || 0);
});

// Handle errors
proxy.on('error', (err) => {
  console.error(`[CFPB MCP] Error spawning proxy:`, err);
  process.exit(1);
});
```

**Key decisions**:

* Logs to stderr (stdout reserved for MCP protocol)
* Inherits stdio for transparent piping
* Forwards exit codes properly
* No additional dependencies (uses Node builtins only)

### 3. `package.json` (Optional)

**Purpose**: Declares package metadata (not strictly required for MCPB but good practice).

```json
{
  "name": "cfpb-mcp-extension",
  "version": "1.0.0",
  "description": "Claude Desktop Extension for CFPB Consumer Complaints MCP Server",
  "main": "server/index.js",
  "license": "MIT",
  "private": true,
  "engines": {
    "node": ">=16.0.0"
  }
}
```

### 4. `extension/README.md`

**Purpose**: Document extension usage and configuration.

```markdown
# CFPB Consumer Complaints - Claude Desktop Extension

Local MCP extension for accessing CFPB consumer complaint data.

## Installation

1. Download `cfpb-complaints.mcpb`
2. Open Claude Desktop
3. Go to Settings > Extensions
4. Drag and drop the `.mcpb` file
5. Configure the server URL (default: http://localhost:8000/mcp/sse)

## Requirements

- CFPB MCP server running locally or remotely
- Node.js 16+ (bundled with Claude Desktop)

## Configuration

**Server URL**: Point to your CFPB MCP server instance
- Local development: `http://localhost:8000/mcp/sse`
- Remote server: `https://your-server.com/mcp/sse`

## Available Tools

- `search_complaints` - Search consumer complaints
- `list_complaint_trends` - Analyze trends over time
- `get_state_aggregations` - Geographic complaint data
- `get_complaint_document` - Retrieve specific complaints
- `suggest_filter_values` - Autocomplete for filters
- `generate_cfpb_dashboard_url` - Links to official CFPB UI
- `get_overall_trend_signals` - Detect anomalies
- `rank_group_spikes` - Product/issue spike detection
- `rank_company_spikes` - Company spike detection

## Troubleshooting

**Extension won't connect:**
- Ensure server URL is correct and includes `/mcp/sse`
- Verify CFPB server is running
- Check server logs for connection attempts

**Tools not appearing:**
- Restart Claude Desktop
- Reinstall the extension
- Check extension logs in Claude Desktop settings
```

## Build Process

### Prerequisites

```bash
npm install -g @anthropic-ai/mcpb
```

### Build Steps

1. **Create extension directory**:
   ```bash
   mkdir -p extension/server
   ```

2. **Copy files**:
   ```bash
   # Create all files listed above in extension/
   ```

3. **Validate manifest**:
   ```bash
   cd extension
   mcpb validate
   ```

4. **Package extension**:

   ```bash
   mcpb pack
   ```

   This creates `cfpb-complaints.mcpb` (a ZIP archive)

5. **Output location**:
   ```
   extension/cfpb-complaints.mcpb
   ```

## Testing Plan

### Local Testing (Pre-Installation)

1. **Validate manifest schema**:
   ```bash
   mcpb validate
   ```

2. **Test index.js directly**:
   ```bash
   REMOTE_MCP_URL=http://localhost:8000/mcp/sse node server/index.js
   ```
   * Should connect to server
   * Should relay MCP messages on stdio

### Installation Testing

1. **Install in Claude Desktop**:
   * Drag `.mcpb` into Settings > Extensions
   * Configure server URL
   * Enable extension

2. **Verify tool discovery**:
   * All 9 tools should appear in Claude's tool list
   * Tool descriptions should match manifest

3. **Test tool execution**:
   * Run: "Search for mortgage complaints in California"
   * Verify: Tool call reaches remote server
   * Check: Response returns correctly through proxy
   * Confirm: Server logs show the request

4. **Test error handling**:
   * Stop CFPB server
   * Attempt tool call
   * Verify: Graceful error message (not crash)

5. **Test reconnection**:
   * Restart CFPB server
   * Verify: Extension reconnects automatically

### Multi-Platform Testing

* **macOS**: Primary platform
* **Windows**: Verify `npx` works correctly
* **Linux**: Test if available

## Success Criteria

✅ Extension installs via drag-and-drop
✅ User can configure server URL
✅ All 9 tools appear in Claude
✅ Tool calls execute successfully
✅ Responses format correctly
✅ Server logs show proxied requests
✅ No local MCP logic (pure proxy)
✅ Extension survives server restarts
✅ Clear error messages when server unavailable

## Known Limitations (Phase 1)

* No authentication (pass-through only)
* HTTP only (HTTPS in Phase 2)
* Single server URL (no failover)
* No request caching
* Requires internet for `npx -y` first run

## Migration to Phase 2

When ready for Phase 2 (Remote MCP Connector):

1. **HTTPS deployment**:
   * Deploy server with TLS
   * Update default URL in manifest

2. **Authentication**:
   * Add API key or OAuth to server
   * Update manifest to collect credentials
   * Pass auth headers via `mcp-remote --header`

3. **Connector registration**:
   * Use same `/mcp/sse` endpoint
   * Register via Claude Custom Connectors UI
   * Deprecate local `.mcpb` once connector is live

4. **Backward compatibility**:
   * `.mcpb` continues to work for local/dev
   * Same server supports both paths

## Automation & Scripting

### Future: Parameterized Build Script

Create `scripts/build_extension.sh`:

```bash
#!/bin/bash
# Build CFPB MCP extension with configurable settings

VERSION=${1:-1.0.0}
SERVER_URL=${2:-http://localhost:8000/mcp/sse}

# Update manifest.json with parameters
jq ".version = \"$VERSION\" | .user_config.remote_url.default = \"$SERVER_URL\"" \
  extension/manifest.json > extension/manifest.json.tmp
mv extension/manifest.json.tmp extension/manifest.json

# Package
cd extension
mcpb pack
echo "Built cfpb-complaints.mcpb (v$VERSION, default URL: $SERVER_URL)"
```

Usage:

```bash
# Dev build
./scripts/build_extension.sh 1.0.0 http://localhost:8000/mcp/sse

# Production build
./scripts/build_extension.sh 1.0.0 https://cfpb-mcp.example.com/mcp/sse
```

## File Checklist

* \[ ] `extension/manifest.json` (complete metadata)
* \[ ] `extension/server/index.js` (npx mcp-remote wrapper)
* \[ ] `extension/package.json` (optional but recommended)
* \[ ] `extension/README.md` (user documentation)
* \[ ] Validate with `mcpb validate`
* \[ ] Build with `mcpb pack`
* \[ ] Test installation in Claude Desktop
* \[ ] Verify all tools work end-to-end
* \[ ] Document in main README.md

## Next Steps

1. Create extension directory structure
2. Write all files per specifications above
3. Install `@anthropic-ai/mcpb` toolchain
4. Validate manifest
5. Package `.mcpb` file
6. Test in Claude Desktop
7. Document installation in main README
8. Commit to git under `extension/` directory

***

**Timeline**: ~2 hours for implementation + testing\
**Complexity**: Low (leveraging existing tools)\
**Risk**: Minimal (pure proxy, no custom logic)
