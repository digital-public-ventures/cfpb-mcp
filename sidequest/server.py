import os

from fastmcp import FastMCP

mcp = FastMCP('Demo')


@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


if __name__ == '__main__':
    host = os.environ.get('FAST_MCP_HOST', '127.0.0.1')
    port = int(os.environ.get('FAST_MCP_PORT', '8765'))
    path = os.environ.get('FAST_MCP_PATH', '/mcp')
    mcp.run(transport='http', host=host, port=port, path=path)
