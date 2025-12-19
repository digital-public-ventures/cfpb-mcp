import json

import pytest

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


@pytest.mark.asyncio
async def test_mcp_can_connect_and_list_tools(server_url: str):
    async with sse_client(f"{server_url}/mcp/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()

    names = {t.name for t in result.tools}
    assert {
        "search_complaints",
        "list_complaint_trends",
        "get_state_aggregations",
        "get_complaint_document",
        "suggest_filter_values",
    }.issubset(names)


@pytest.mark.asyncio
async def test_mcp_search_complaints_works(server_url: str):
    async with sse_client(f"{server_url}/mcp/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            res = await session.call_tool("search_complaints", {"size": 1})

    assert res.isError is False

    # FastMCP typically returns JSON in structuredContent when possible.
    payload = res.structuredContent
    if payload is None:
        # Fallback: try to parse text blocks.
        joined = "\n".join(getattr(b, "text", "") for b in res.content)
        payload = json.loads(joined)

    assert isinstance(payload, dict)
    # Phase 4.6: responses are wrapped with citations
    assert "data" in payload
    assert "citations" in payload
    assert isinstance(payload["citations"], list)
    assert "hits" in payload["data"]


@pytest.mark.asyncio
async def test_mcp_document_round_trip(server_url: str):
    async with sse_client(f"{server_url}/mcp/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            search = await session.call_tool("search_complaints", {"size": 1})
            assert search.isError is False
            search_payload = search.structuredContent
            if search_payload is None:
                joined = "\n".join(getattr(b, "text", "") for b in search.content)
                search_payload = json.loads(joined)

            # Phase 4.6: responses are wrapped with data/citations
            search_data = search_payload.get("data", search_payload)
            hits = search_data.get("hits", {}).get("hits", [])
            assert hits
            hit = hits[0]
            complaint_id = hit.get("_id") or hit.get("_source", {}).get("complaint_id")
            assert complaint_id

            doc = await session.call_tool(
                "get_complaint_document", {"complaint_id": complaint_id}
            )

    assert doc.isError is False
    assert isinstance(doc.structuredContent or doc.content, object)
