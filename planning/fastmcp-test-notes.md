# FASTMCP NOTES

If you are strictly using **Streamable HTTP**, the redirects and mounting errors are almost always caused by **trailing slash mismatches** or **FastAPI's automatic doc redirection**.

Here is how to fix the integration test loop and correctly package the app without worrying about the SSE handler.

### 1. The Server Fix (`src/server.py`)

To prevent "app mounting" issues, you should explicitly create a standard FastAPI `app` and **mount** FastMCP (or its router) onto it. This gives you full control over the routes and prevents FastMCP from hijacking the root `/` with its own redirect logic.

```python
from fastapi import FastAPI
from fastmcp import FastMCP

# 1. Create a standard FastAPI app (You control this)
app = FastAPI()

# 2. Create your FastMCP instance
mcp = FastMCP("My Agent")

@mcp.tool
def calculate(a: int, b: int) -> int:
    return a + b

# 3. Explicitly Include the MCP Router
# Instead of letting FastMCP be the "main" app, just grab its router.
# This prevents it from installing default root redirects you don't want.
app.include_router(mcp._fastapi_app.router)

# 4. (Optional) Define a simple root to stop 404s/Redirects
@app.get("/")
def health_check():
    return {"status": "ok", "mode": "streamable-http"}

```

### 2. The Test Fix (`tests/test_server.py`)

The "Redirect" error usually happens because `TestClient` hits `http://testserver/` but the app redirects to `https` or `/docs`.

Use this setup to debug exactly what is happening:

```python
from fastapi.testclient import TestClient
from src.server import app

def test_routes_are_mounted():
    # Print routes to verify where things actually live
    print("\n--- Mounted Routes ---")
    for route in app.routes:
        print(f"{route.path} [{','.join(route.methods)}]")
    print("----------------------\n")

    # Disable redirect following to see the REAL error (307 vs 200)
    with TestClient(app) as client:
        # 1. Test your Health Check (Should be 200, not 307)
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "mode": "streamable-http"}

        # 2. Test a Tool execution via the MCP 'messages' endpoint (POST)
        # Note: If you aren't using SSE, you interact via JSON-RPC POST.
        # Ensure you use the correct JSON-RPC 2.0 payload.
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "calculate",
                "arguments": {"a": 10, "b": 20}
            },
            "id": 1
        }
        
        # FastMCP typically mounts the message handler at /messages or /jsonrpc
        # Check the print output from above to confirm the path.
        # It is often "/mcp/messages" or just "/messages" depending on version.
        # We try "/messages" here:
        response = client.post("/messages", json=payload)
        
        # If you get a 307 here, try "/messages/" (add slash)
        if response.status_code == 307:
            print(f"Redirecting to: {response.headers['location']}")
            
        assert response.status_code == 200
        assert response.json()["result"]["content"][0]["text"] == "30"

```

### 3. Common Pitfalls Checklist

1. **Slash Strictness:**

* FastAPI is strict. `/messages` is NOT the same as `/messages/`.
* If you mount the app and get a 307, **add or remove the trailing slash** in your test request.

2. **The "Docs" Redirect:**

* By default, FastAPI redirects `GET /` to `/docs`.
* If your test expects 200 OK on `/`, it will fail. Defining the explicit `@app.get("/")` above fixes this.

3. **Dependency Conflicts:**

* Since you aren't using SSE, you don't need to "connect" via a client in your test. Just POST valid JSON-RPC to the endpoint.

### 4. Cloudflare Consideration

Since you manually created `app = FastAPI()` in step 1, your `wrangler.toml` and packaging remain exactly the same. Cloudflare's Python runtime will find the `app` object and serve it correctly without trying to initialize the FastMCP internal server.
