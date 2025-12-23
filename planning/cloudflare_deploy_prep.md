# Package FastMCP server for Cloudflare Workers

Since you are removing the Playwright dependency, this becomes a straightforward Python Worker deployment. Cloudflare's Python runtime (Pyodide) handles FastAPI and Pydantic (used by FastMCP) natively.

## 1. Directory Structure

Organize your project so Cloudflare knows exactly where to look.

```text
my-mcp-server/
├── src/
│   ├── server.py        # Your main FastMCP definition
│   └── utils.py         # Your helper functions
├── requirements.txt     # Cleaned dependencies
└── wrangler.toml        # Deployment config

```

## 2. Configuration Files

**`requirements.txt`**
Remove Playwright. Cloudflare will install these packages into the Worker environment automatically.

```text
fastapi>=0.125.0
fastmcp>=2.0.0
httpx>=0.28.1
mcp>=1.24.0
uvicorn[standard]>=0.38.0

```

*(Note: `uvicorn` won't actually be used by Cloudflare—the Worker runtime acts as the server—but keeping it allows you to test locally.)*

**`wrangler.toml`**
This file tells Cloudflare to use the Python runtime.

```toml
name = "fastmcp-server"
main = "src/server.py"
compatibility_date = "2025-12-01"
compatibility_flags = ["python_workers"]

```

## 3. The Server Code (`src/server.py`)

This is the most critical part. Cloudflare Workers do not execute `if __name__ == "__main__":` blocks. Instead, they look for an ASGI application object named `app` (or similar) to handle incoming requests.

You must explicitly expose the underlying FastAPI app from your FastMCP instance.

```python
from fastmcp import FastMCP
from . import utils  # Relative import for your local utilities file

# Initialize FastMCP
mcp = FastMCP("My Agent")

# Define your tools/resources
@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return utils.helper_math_func(a, b)


# ---------------------------------------------------------
# CRITICAL FOR CLOUDFLARE DEPLOYMENT
# ---------------------------------------------------------
# Cloudflare needs the ASGI app object, not the mcp runner.
# FastMCP typically exposes the underlying FastAPI app via a property.
# Depending on the specific FastMCP version, it is usually `mcp._fastapi_app` 
# or you can mount it explicitly.

app = mcp._fastapi_app 

# If your specific version of FastMCP doesn't expose `_fastapi_app`, 
# you can access it via the internal mount:
# app = mcp.fastapi

```

## 4. Deployment

1. **Test Locally:**
   You can still run this locally using the standard command since `uvicorn` is in your requirements:

   ```bash
   uvicorn src.server:app --reload
   ```

2. **Deploy to Cloudflare:**
   Run the wrangler command from the root directory (where `wrangler.toml` is):

   ```bash
   npx wrangler deploy
   ```

## Summary of Changes

1. **Commented out Playwright:** Solves the binary/OS compatibility issue.
2. **Exposed `app`:** Replaced `mcp.run()` with `app = mcp._fastapi_app` so Cloudflare's ASGI adapter can serve the requests.
3. **Relative Imports:** Ensured `utils.py` is imported correctly (`from . import utils`) so it resolves within the Worker's module system.
