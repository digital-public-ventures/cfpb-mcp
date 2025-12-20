import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

pytestmark = pytest.mark.anyio


async def test_http_transport_list_tools(server_url: str) -> None:
    """Verify that the Streamable HTTP endpoint (POST /mcp) works."""
    url = f"{server_url}/mcp"
    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as mcp:
            await mcp.initialize()
            tools = await mcp.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            assert "search_complaints" in tool_names


async def test_http_transport_access_control(server_url: str) -> None:
    """Verify that the Streamable HTTP endpoint is protected by the middleware."""
    url = f"{server_url}/mcp"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        assert response.status_code == 405
