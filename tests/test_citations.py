from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator, Mapping
from datetime import date
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from citations_mapping import build_deeplink_url, map_api_params_to_url_params
from server import BASE_URL
from tests.playwright_helpers import fast_playwright_context
from utils.deeplink_mapping import (
    TRENDS_ENDPOINT_KEYS,
    apply_default_dates,
    validate_api_params,
)

FAST_URL_CASES = [
    pytest.param(
        {
            'search_term': 'mortgage',
            'field': 'all',
            'size': 25,
            'sort': 'created_date_desc',
            'frm': 0,
        },
        id='example-simple-search',
        marks=pytest.mark.slow,
    ),
    pytest.param(
        {
            'product': ['Credit card'],
            'state': ['CA'],
            'date_received_min': '2023-01-01',
            'date_received_max': '2023-12-31',
            'size': 50,
            'frm': 50,
        },
        id='example-filtered-list',
        marks=pytest.mark.slow,
    ),
]

SLOW_URL_CASES = [
    pytest.param(
        {
            'search_term': 'forbearance',
            'field': 'all',
            'product': ['Mortgage'],
            'company_response': ['Closed with explanation'],
            'state': ['TX'],
            'size': 10,
            'sort': 'created_date_desc',
            'frm': 0,
        },
        id='example-filtered-search',
        marks=pytest.mark.slow,
    ),
    pytest.param(
        {
            'search_term': 'credit card',
            'field': 'all',
            'tags': ['Older American'],
            'consumer_disputed': ['yes'],
            'has_narrative': 'true',
            'size': 10,
            'sort': 'created_date_desc',
            'frm': 0,
        },
        id='example-tags-disputed',
        marks=pytest.mark.slow,
    ),
]

EXTRA_SLOW_URL_CASES = [
    pytest.param(
        {
            'search_term': 'debt collection',
            'field': 'all',
            'product': ['Debt collection', 'Credit card'],
            'state': ['CA', 'NY'],
            'company_response': ['Closed with explanation'],
            'consumer_disputed': ['yes'],
            'has_narrative': 'true',
            'size': 10,
            'sort': 'created_date_desc',
            'frm': 0,
        },
        id='example-multi-filter',
        marks=[pytest.mark.slow, pytest.mark.extra_slow],
    ),
]

EXAMPLE_API_QUERIES = FAST_URL_CASES + SLOW_URL_CASES + EXTRA_SLOW_URL_CASES

EXAMPLE_TREND_QUERY = {
    'lens': 'product',
    'trend_interval': 'month',
    'trend_depth': 5,
    'date_received_min': '2022-01-01',
    'date_received_max': '2022-12-31',
    'product': ['Mortgage'],
}

FIXED_TODAY = date(2025, 12, 20)

UI_MATCH_PATTERNS = [
    re.compile(
        r'Showing\s+([\d,]+)\s+matches\s+out of\s+[\d,]+\s+total complaints',
        re.IGNORECASE,
    ),
    re.compile(
        r'Showing\s+([\d,]+)\s+matches\s+out of\s+[\d,]+\s+complaints',
        re.IGNORECASE,
    ),
]


def _parse_query(url: str) -> dict[str, list[str]]:
    parsed = urlparse(url)
    return parse_qs(parsed.query)


def _parse_ui_matches(ui_text: str) -> int:
    for pattern in UI_MATCH_PATTERNS:
        match = pattern.search(ui_text)
        if match:
            return int(match.group(1).replace(',', ''))
    raise ValueError('Unable to locate matches-out-of count in UI text.')


async def _fetch_api_total(client: httpx.AsyncClient, api_params: Mapping[str, Any]) -> int:
    response = await client.get(BASE_URL, params=api_params)
    if response.status_code != 200:
        pytest.fail(f'API call failed: {response.url} ({response.status_code})')

    data = response.json()
    total = data.get('hits', {}).get('total', 0)
    if isinstance(total, dict):
        total = total.get('value', 0)
    if isinstance(total, str) and total.isdigit():
        total = int(total)
    if not isinstance(total, int):
        pytest.fail(f'Unexpected API total format: {total}')
    return cast('int', total)


@pytest.fixture(scope='module')
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        yield client


@pytest.fixture(scope='module')
async def ui_context():
    try:
        async with fast_playwright_context() as context:
            yield context
    except RuntimeError as exc:
        pytest.skip(str(exc))


@pytest.mark.fast
def test_map_api_params_to_url_params_examples():
    api_params = {
        'search_term': 'mortgage',
        'field': 'all',
        'size': 25,
        'sort': 'created_date_desc',
        'frm': 0,
    }
    mapped = map_api_params_to_url_params(api_params)
    assert mapped['searchText'] == 'mortgage'
    assert mapped['searchField'] == 'all'
    assert mapped['size'] == 25
    assert mapped['sort'] == 'created_date_desc'

    url = build_deeplink_url(api_params, today=FIXED_TODAY)
    query = _parse_query(url)
    assert query['page'] == ['1']

    api_params = {
        'product': ['Credit card'],
        'state': ['CA'],
        'date_received_min': '2023-01-01',
        'date_received_max': '2023-12-31',
        'size': 50,
        'frm': 50,
    }
    url = build_deeplink_url(api_params, today=FIXED_TODAY)
    query = _parse_query(url)
    assert query['product'] == ['Credit card']
    assert query['state'] == ['CA']
    assert query['date_received_min'] == ['2023-01-01']
    assert query['date_received_max'] == ['2023-12-31']
    assert query['page'] == ['2']


@pytest.mark.fast
def test_trend_mapping_defaults():
    url = build_deeplink_url(EXAMPLE_TREND_QUERY, today=FIXED_TODAY)
    query = _parse_query(url)
    assert query['tab'] == ['Trends']
    assert query['lens'] == ['product']
    assert query['dateInterval'] == ['Month']
    assert query['trend_depth'] == ['5']

    validation = validate_api_params(EXAMPLE_TREND_QUERY, TRENDS_ENDPOINT_KEYS)
    assert not validation.unknown_keys


@pytest.mark.fast
def test_default_date_window():
    params = apply_default_dates({}, today=FIXED_TODAY)
    assert params['date_received_min'] == '2011-12-01'
    assert params['date_received_max'] == '2025-10-31'


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.anyio
@pytest.mark.parametrize('api_params', EXAMPLE_API_QUERIES)
async def test_ui_vs_api_counts(api_params, api_client, ui_context):
    api_params_with_dates = apply_default_dates(api_params, today=FIXED_TODAY)
    url = build_deeplink_url(api_params_with_dates, tab='List', today=FIXED_TODAY)

    api_task = asyncio.create_task(_fetch_api_total(api_client, api_params_with_dates))
    page = await ui_context.new_page()
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        try:
            await page.wait_for_function(
                'document.body && /matches out of/i.test(document.body.innerText)',
                timeout=20000,
            )
        except Exception:
            pass
        ui_text = await page.inner_text('body')
    finally:
        await page.close()

    api_total = await api_task
    ui_matches = _parse_ui_matches(ui_text)

    assert api_total == ui_matches, (
        f'API/UI match count mismatch: api_total={api_total} ui_matches={ui_matches} url={url}'
    )
