import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

pytestmark = pytest.mark.anyio


def _default_date_window() -> tuple[str, str, str]:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    date_received_max = month_start.strftime('%Y-%m-%d')
    date_received_min = f'{now.year - 2:04d}-{now.month:02d}-01'
    current_month_prefix = f'{now.year:04d}-{now.month:02d}-'
    return date_received_min, date_received_max, current_month_prefix


def _coerce_json(payload: object) -> object:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def _tool_payload(result: object) -> object:
    payload = getattr(result, 'structuredContent', None) or getattr(result, 'content', None)
    if isinstance(payload, list):
        text_parts = []
        for item in payload:
            text = getattr(item, 'text', None)
            if text:
                text_parts.append(text)
        if text_parts:
            return _coerce_json('\n'.join(text_parts))
    if isinstance(payload, dict) and set(payload.keys()) == {'result'}:
        return payload['result']
    return _coerce_json(payload)


def _extract_complaint_id_from_search_payload(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get('data') if isinstance(payload.get('data'), dict) else None
    if not isinstance(data, dict):
        return None
    hits = data.get('hits', {})
    if not isinstance(hits, dict):
        return None
    inner = hits.get('hits', [])
    if not isinstance(inner, list) or not inner:
        return None
    hit0 = inner[0] if isinstance(inner[0], dict) else None
    if not hit0:
        return None
    cid = hit0.get('_id') or (hit0.get('_source', {}) if isinstance(hit0.get('_source'), dict) else {}).get(
        'complaint_id'
    )
    if cid is None:
        return None
    try:
        cid_int = int(str(cid))
    except ValueError:
        return None
    if 4 <= len(str(cid_int)) <= 9:
        return cid_int
    return None


async def _with_mcp(server_url: str, action: Callable[[ClientSession], Awaitable[None]]) -> None:
    mcp_url = f'{server_url}/mcp'
    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as mcp:
            await mcp.initialize()
            await action(mcp)


async def test_tools_list_smoke(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        tools = await mcp.list_tools()
        tool_names = {tool.name for tool in tools.tools}
        assert 'search_complaints' in tool_names
        assert 'list_complaint_trends' in tool_names
        assert 'get_state_aggregations' in tool_names
        assert 'suggest_filter_values' in tool_names
        assert 'get_complaint_document' in tool_names
        assert 'generate_cfpb_dashboard_url' in tool_names
        assert 'capture_cfpb_chart_screenshot' in tool_names

    await _with_mcp(server_url, _run)


async def test_search_smoke(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        result = await mcp.call_tool('search_complaints', {'size': 1})
        payload = _tool_payload(result)
        assert isinstance(payload, dict)
        data = payload.get('data')
        assert isinstance(data, dict)
        assert 'hits' in data

    await _with_mcp(server_url, _run)


async def test_trends_smoke(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        result = await mcp.call_tool('list_complaint_trends', {'trend_depth': 5})
        payload = _tool_payload(result)
        assert isinstance(payload, dict)
        data = payload.get('data')
        assert isinstance(data, dict)

    await _with_mcp(server_url, _run)


async def test_geo_states_smoke(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        result = await mcp.call_tool('get_state_aggregations', {})
        payload = _tool_payload(result)
        assert isinstance(payload, dict)
        data = payload.get('data')
        assert isinstance(data, dict)

    await _with_mcp(server_url, _run)


@pytest.mark.parametrize('field', ['company', 'zip_code'])
async def test_suggest_smoke(server_url: str, field: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        result = await mcp.call_tool(
            'suggest_filter_values',
            {'field': field, 'text': 'bank' if field == 'company' else '90', 'size': 3},
        )
        payload = _tool_payload(result)
        if isinstance(payload, str):
            payload = [line.strip() for line in payload.splitlines() if line.strip()]
        assert isinstance(payload, list)
        assert len(payload) <= 3

    await _with_mcp(server_url, _run)


async def test_document_round_trip_from_search(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        search_result = await mcp.call_tool('search_complaints', {'size': 1})
        payload = _tool_payload(search_result)
        complaint_id = _extract_complaint_id_from_search_payload(payload)
        assert complaint_id is not None, 'Expected a complaint id from search results'

        doc_result = await mcp.call_tool('get_complaint_document', {'complaint_id': str(complaint_id)})
        doc_payload = _tool_payload(doc_result)
        assert isinstance(doc_payload, dict)

    await _with_mcp(server_url, _run)


async def test_signals_overall_smoke(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        date_min, date_max, current_month_prefix = _default_date_window()
        result = await mcp.call_tool(
            'get_overall_trend_signals',
            {'date_received_min': date_min, 'date_received_max': date_max},
        )
        payload = _tool_payload(result)
        assert isinstance(payload, dict)
        overall = (payload.get('signals') or {}).get('overall')
        assert isinstance(overall, dict)
        last_bucket = overall.get('last_bucket')
        assert isinstance(last_bucket, dict)
        assert not str(last_bucket.get('label', '')).startswith(current_month_prefix)

    await _with_mcp(server_url, _run)


@pytest.mark.parametrize('group', ['product', 'issue'])
async def test_signals_group_smoke(server_url: str, group: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        date_min, date_max, _ = _default_date_window()
        result = await mcp.call_tool(
            'rank_group_spikes',
            {
                'group': group,
                'date_received_min': date_min,
                'date_received_max': date_max,
                'top_n': 5,
            },
        )
        payload = _tool_payload(result)
        assert isinstance(payload, dict)
        results = payload.get('results')
        assert isinstance(results, list)
        assert len(results) <= 5
        if results:
            row0 = results[0]
            assert isinstance(row0, dict)
            assert 'group' in row0
            assert 'signals' in row0

    await _with_mcp(server_url, _run)


async def test_signals_company_smoke(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        date_min, date_max, _ = _default_date_window()
        result = await mcp.call_tool(
            'rank_company_spikes',
            {
                'date_received_min': date_min,
                'date_received_max': date_max,
                'top_n': 5,
            },
        )
        payload = _tool_payload(result)
        assert isinstance(payload, dict)
        results = payload.get('results')
        assert isinstance(results, list)
        assert len(results) <= 5
        if results:
            row0 = results[0]
            assert isinstance(row0, dict)
            assert 'company' in row0
            assert 'computed' in row0

    await _with_mcp(server_url, _run)


async def test_generate_cfpb_dashboard_url(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        result = await mcp.call_tool(
            'generate_cfpb_dashboard_url',
            {'search_term': 'foreclosure', 'product': ['Mortgage']},
        )
        payload = _tool_payload(result)
        if isinstance(payload, dict) and 'result' in payload:
            payload = payload['result']
        assert isinstance(payload, str)
        assert payload.startswith('https://www.consumerfinance.gov/data-research/consumer-complaints/search/')
        assert 'searchText=foreclosure' in payload

    await _with_mcp(server_url, _run)


async def test_capture_cfpb_chart_screenshot(server_url: str) -> None:
    async def _run(mcp: ClientSession) -> None:
        try:
            result = await mcp.call_tool(
                'capture_cfpb_chart_screenshot',
                {'search_term': 'mortgage', 'product': ['Mortgage']},
            )
        except Exception as exc:
            message = str(exc).lower()
            if 'playwright' in message or 'browser unavailable' in message:
                pytest.skip('Playwright not available for screenshot test')
            raise

        payload = _tool_payload(result)
        if isinstance(payload, dict) and 'result' in payload:
            payload = payload['result']
        assert isinstance(payload, str)
        assert len(payload) > 1000

    await _with_mcp(server_url, _run)
