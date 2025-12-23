import os

import uvicorn
from fastapi import FastAPI
from fastmcp import FastMCP

mcp = FastMCP('Notes Demo')


@mcp.tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


mcp_app = mcp.http_app(path='/', transport='streamable-http')
app = FastAPI(lifespan=mcp_app.lifespan)
app.mount('/mcp', mcp_app)


@app.get('/')
def health_check() -> dict[str, str]:
    return {'status': 'ok', 'mode': 'streamable-http'}


if __name__ == '__main__':
    host = os.environ.get('FAST_MCP_HOST', '127.0.0.1')
    port = int(os.environ.get('FAST_MCP_PORT', '8766'))
    uvicorn.run(app, host=host, port=port, log_level='warning')
