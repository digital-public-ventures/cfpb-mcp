from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import time
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from mcp.server.fastmcp import FastMCP
from playwright.async_api import (
    Browser,
    async_playwright,
)
from playwright.async_api import (
    Error as PlaywrightError,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)
from starlette.responses import Response

from utils.deeplink_mapping import build_deeplink_url

BASE_URL = 'https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/'

SearchField = Literal['complaint_what_happened', 'company', 'all']
SearchSort = Literal['relevance_desc', 'created_date_desc']

MIN_STDDEV_SAMPLES = 2
MIN_SIGNAL_POINTS = 2
MIN_BASELINE_POINTS = 2
CHART_MIN_WIDTH = 400
CHART_MIN_HEIGHT = 300
SCREENSHOT_UNAVAILABLE_DETAIL = 'Screenshot service unavailable (Playwright not initialized)'
_BOOL_LITERALS = {'true', 'false'}


def _normalize_scalar(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        lowered = stripped.lower()
        if lowered in _BOOL_LITERALS:
            return lowered
        return stripped
    return value


def _normalize_list(values: list[Any]) -> list[Any] | None:
    normalized: list[Any] = []
    for item in values:
        cleaned = _normalize_scalar(item)
        if cleaned is None:
            continue
        normalized.append(cleaned)
    return normalized or None


def prune_params(params: dict[str, Any]) -> dict[str, Any]:
    """Remove None/empty values so we don't send invalid query params upstream.

    This is particularly important for LLM tool calls that may pass empty strings
    or lists containing empty strings.
    """
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        normalized = _normalize_list(value) if isinstance(value, list) else _normalize_scalar(value)
        if normalized is None:
            continue
        cleaned[key] = normalized

    return cleaned


def _schedule_debug_file_cleanup(path: Path, delay_seconds: float = 300.0) -> None:
    def _cleanup() -> None:
        with suppress(OSError):
            path.unlink()

    timer = threading.Timer(delay_seconds, _cleanup)
    timer.daemon = True
    timer.start()


def build_params(
    *,
    search_term: str | None = None,
    field: str | None = None,
    company: list[str] | None = None,
    company_public_response: list[str] | None = None,
    company_response: list[str] | None = None,
    consumer_consent_provided: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    company_received_min: str | None = None,
    company_received_max: str | None = None,
    has_narrative: list[str] | None = None,
    issue: list[str] | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    submitted_via: list[str] | None = None,
    tags: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
) -> dict[str, Any]:
    """Build CFPB search API query parameters.

    This is a thin wrapper around `prune_params` that assembles the known filter
    keys for the upstream CFPB search endpoint.
    """
    params: dict[str, Any] = {
        'search_term': search_term,
        'field': field,
        'company': company,
        'company_public_response': company_public_response,
        'company_response': company_response,
        'consumer_consent_provided': consumer_consent_provided,
        'consumer_disputed': consumer_disputed,
        'date_received_min': date_received_min,
        'date_received_max': date_received_max,
        'company_received_min': company_received_min,
        'company_received_max': company_received_max,
        'has_narrative': has_narrative,
        'issue': issue,
        'product': product,
        'state': state,
        'submitted_via': submitted_via,
        'tags': tags,
        'timely': timely,
        'zip_code': zip_code,
    }
    return prune_params(params)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App lifespan: initialize shared HTTP client + optional Playwright."""
    # Initialize FastMCP lifespans (critical for session management)
    async with AsyncExitStack() as stack:
        # We must initialize the lifecycle of the FastMCP apps we are using.
        # This ensures internal task groups and session managers are started.
        # We pass the sub-app itself to its lifespan context.
        if hasattr(_http_app.router, 'lifespan_context'):
            await stack.enter_async_context(_http_app.router.lifespan_context(_http_app))

        # A single shared client for connection pooling.
        app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

        # Initialize Playwright for screenshot service (Phase 4.5)
        app.state.playwright = None
        app.state.browser = None
        try:
            pw = await async_playwright().start()
            app.state.playwright = pw
            app.state.browser = await pw.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                ],
            )
        except Exception as e:
            # If Playwright isn't available (e.g., in minimal test env), log and continue.
            # The screenshot endpoints will return 503.
            print(f'Warning: Playwright initialization failed: {e}', file=sys.stderr)

        try:
            yield
        finally:
            await app.state.http.aclose()
            if app.state.browser:
                try:
                    await app.state.browser.close()
                except Exception as e:
                    print(f'Warning: Playwright browser.close failed: {e}', file=sys.stderr)
            if app.state.playwright:
                try:
                    await app.state.playwright.stop()
                except Exception as e:
                    print(f'Warning: Playwright stop failed: {e}', file=sys.stderr)


# 1) Initialize FastAPI and MCP (single app, two interfaces)
app = FastAPI(
    title='CFPB Complaint API',
    description='A hybrid MCP/REST server for accessing the Consumer Complaint Database.',
    version='1.0.0',
    lifespan=lifespan,
)
server = FastMCP(
    'cfpb-complaints',
    # Important for Phase 5.2: FastMCP auto-enables DNS rebinding protection
    # (Host header allowlist) when host is localhost. When running behind a
    # tunnel with a public hostname, preserve compatibility by matching the
    # runtime bind host here as well.
    host=os.getenv('CFPB_MCP_HOST', '127.0.0.1'),
)


def _get_allowed_api_keys() -> set[str]:
    raw = (os.getenv('CFPB_MCP_API_KEYS') or '').strip()
    if not raw:
        return set()
    return {k.strip() for k in raw.split(',') if k.strip()}


def _hash_key_prefix(api_key: str) -> str:
    if not api_key:
        return 'none'
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:8]


class _TokenBucket:
    def __init__(self, *, capacity: float, refill_per_sec: float, now: float) -> None:
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self.tokens = float(capacity)
        self.last = float(now)

    def consume(self, *, now: float, amount: float = 1.0) -> bool:
        now = float(now)
        elapsed = max(0.0, now - self.last)
        self.last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, _TokenBucket] = {}


def _rate_limit_allows(bucket_id: str) -> bool:
    rps = float(os.getenv('CFPB_MCP_RATE_LIMIT_RPS', '0') or '0')
    burst = float(os.getenv('CFPB_MCP_RATE_LIMIT_BURST', '0') or '0')
    if rps <= 0 or burst <= 0:
        return True

    now = time.monotonic()
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.get(bucket_id)
        if bucket is None:
            bucket = _TokenBucket(capacity=burst, refill_per_sec=rps, now=now)
            _RATE_LIMIT_BUCKETS[bucket_id] = bucket
        return bucket.consume(now=now)


def _audit_log(event: dict[str, Any]) -> None:
    # Best-effort JSONL to stderr (good for container logs / cloudflared output).
    try:
        print(json.dumps(event, separators=(',', ':'), default=str), file=sys.stderr)
    except (TypeError, ValueError):
        return


class MCPAccessControlMiddleware:
    """ASGI middleware enforcing auth/rate-limit/audit for /mcp/*.

    This must work for the mounted FastMCP SSE sub-app, so we operate at the ASGI
    layer (rather than FastAPI dependencies).
    """

    def __init__(self, app: ASGIApp) -> None:
        """Store the downstream ASGI app for request handling."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Apply auth/rate-limit checks before dispatching to the MCP app."""
        if scope.get('type') != 'http':
            await self.app(scope, receive, send)
            return

        path = scope.get('path') or ''
        # Phase 5.3: Protect /mcp (Streamable HTTP)
        if path != '/mcp':
            await self.app(scope, receive, send)
            return

        method = (scope.get('method') or '').upper()
        started_at = time.monotonic()
        status_code: int | None = None

        headers = {k.lower(): v for (k, v) in (scope.get('headers') or [])}
        api_key = (headers.get(b'x-api-key') or b'').decode('utf-8', 'replace').strip()

        allowed_keys = _get_allowed_api_keys()
        auth_enabled = bool(allowed_keys)
        key_prefix = _hash_key_prefix(api_key)

        client = scope.get('client')
        client_host = None
        if isinstance(client, list | tuple) and client:
            client_host = client[0]

        def _send_json(status: int, payload: dict[str, Any]) -> Awaitable[None]:
            body = json.dumps(payload, separators=(',', ':')).encode('utf-8')

            async def _do_send() -> None:
                nonlocal status_code
                status_code = status
                await send(
                    {
                        'type': 'http.response.start',
                        'status': status,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'content-length', str(len(body)).encode('ascii')),
                        ],
                    }
                )
                await send({'type': 'http.response.body', 'body': body})

            return _do_send()

        # 1) Auth
        if auth_enabled:
            ok = any(hmac.compare_digest(api_key, k) for k in allowed_keys)
            if not ok:
                await _send_json(
                    401,
                    {
                        'error': {
                            'type': 'auth',
                            'message': 'Missing or invalid API key',
                        }
                    },
                )
                _audit_log(
                    {
                        'ts': datetime.now(timezone.utc).isoformat(),
                        'event': 'mcp_request',
                        'path': path,
                        'method': method,
                        'status': 401,
                        'duration_ms': int((time.monotonic() - started_at) * 1000),
                        'api_key': key_prefix,
                        'client': client_host,
                    }
                )
                return

        # 2) Rate limit
        bucket_id = api_key if api_key else f'anon:{client_host or "unknown"}'
        if not _rate_limit_allows(bucket_id):
            await _send_json(
                429,
                {'error': {'type': 'rate_limit', 'message': 'Too many requests'}},
            )
            _audit_log(
                {
                    'ts': datetime.now(timezone.utc).isoformat(),
                    'event': 'mcp_request',
                    'path': path,
                    'method': method,
                    'status': 429,
                    'duration_ms': int((time.monotonic() - started_at) * 1000),
                    'api_key': key_prefix,
                    'client': client_host,
                }
            )
            return

        # 3) Pass-through + audit
        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message.get('type') == 'http.response.start':
                status_code = int(message.get('status') or 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _audit_log(
                {
                    'ts': datetime.now(timezone.utc).isoformat(),
                    'event': 'mcp_request',
                    'path': path,
                    'method': method,
                    'status': status_code,
                    'duration_ms': int((time.monotonic() - started_at) * 1000),
                    'api_key': key_prefix,
                    'client': client_host,
                }
            )


app.add_middleware(MCPAccessControlMiddleware)


async def _get_json(path: str, *, params: dict[str, Any]) -> Any:
    client: httpx.AsyncClient = app.state.http
    try:
        response = await client.get(path, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc


# -------------------------------------------------------------------------
# 2) Shared Logic (Decoupled from Transport)
# -------------------------------------------------------------------------


async def search_logic(
    *,
    size: int,
    from_index: int,
    sort: str,
    search_after: str | None,
    no_highlight: bool,
    **filters: Any,
) -> Any:
    """Execute a CFPB search query with pagination and filter params."""
    params = build_params(**filters)
    params.update(
        {
            'size': size,
            'frm': from_index,
            'sort': sort,
            'search_after': search_after,
            'no_highlight': no_highlight,
            'no_aggs': False,
        }
    )
    params = prune_params(params)
    return await _get_json(BASE_URL, params=params)


async def trends_logic(
    lens: str,
    trend_interval: str,
    trend_depth: int,
    sub_lens: str | None,
    sub_lens_depth: int,
    focus: str | None,
    **filters: Any,
) -> Any:
    """Execute a CFPB trends query for the requested lens."""
    params = build_params(**filters)
    params.update(
        {
            'lens': lens,
            'trend_interval': trend_interval,
            'trend_depth': trend_depth,
            'sub_lens': sub_lens,
            # Upstream rejects sub_lens_depth when sub_lens is unset.
            'sub_lens_depth': sub_lens_depth if sub_lens is not None else None,
            'focus': focus,
        }
    )
    params = prune_params(params)
    return await _get_json(f'{BASE_URL}trends', params=params)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < MIN_STDDEV_SAMPLES:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return var**0.5


def _current_month_prefix(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return f'{n.year:04d}-{n.month:02d}-'


def _drop_current_month(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    prefix = _current_month_prefix()
    return [(label, count) for (label, count) in points if not str(label).startswith(prefix)]


def _extract_overall_points(payload: Any) -> list[tuple[str, float]]:
    buckets = (payload or {}).get('aggregations', {}).get('dateRangeArea', {}).get('dateRangeArea', {}).get('buckets')
    if not isinstance(buckets, list):
        return []

    rows: list[tuple[int, str, float]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        key = b.get('key')
        label = b.get('key_as_string')
        count = b.get('doc_count')
        if not isinstance(key, int | float) or label is None or not isinstance(count, int | float):
            continue
        rows.append((int(key), str(label), float(count)))

    rows.sort(key=lambda t: t[0])
    return [(label, count) for _, label, count in rows]


def _extract_points_with_key(trend_buckets: list[dict[str, Any]]) -> list[tuple[int | None, str, float]]:
    points_with_key: list[tuple[int | None, str, float]] = []
    for tb in trend_buckets:
        if not isinstance(tb, dict):
            continue
        label = tb.get('key_as_string')
        key = tb.get('key')
        count = tb.get('doc_count')
        if label is None or not isinstance(count, int | float):
            continue
        key_num: int | None = None
        if isinstance(key, int | float):
            key_num = int(key)
        points_with_key.append((key_num, str(label), float(count)))
    return points_with_key


def _extract_group_series(payload: Any, group: str) -> list[dict[str, Any]]:
    group_buckets = (payload or {}).get('aggregations', {}).get(group, {}).get(group, {}).get('buckets')
    if not isinstance(group_buckets, list):
        return []

    out: list[dict[str, Any]] = []
    for b in group_buckets:
        if not isinstance(b, dict):
            continue
        group_key = b.get('key')
        doc_count = b.get('doc_count')
        trend_buckets = b.get('trend_period', {}).get('buckets')
        if group_key is None or not isinstance(trend_buckets, list):
            continue

        # Extract points sorted chronologically by numeric key when present.
        points_with_key = _extract_points_with_key(trend_buckets)
        if any(k is not None for k, _, _ in points_with_key):
            points_with_key.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0))
        else:
            points_with_key.sort(key=lambda t: t[1])

        points = [(label, count) for _, label, count in points_with_key]
        out.append(
            {
                'group': str(group_key),
                'doc_count': doc_count,
                'points': points,
            }
        )

    return out


def _compute_simple_signals(
    points: list[tuple[str, float]],
    *,
    baseline_window: int = 8,
    min_baseline_mean: float = 10.0,
) -> dict[str, Any]:
    if len(points) < MIN_SIGNAL_POINTS:
        return {'error': 'not_enough_points', 'num_points': len(points)}

    labels = [p[0] for p in points]
    values = [p[1] for p in points]

    last_label, last_val = labels[-1], values[-1]
    prev_label, prev_val = labels[-2], values[-2]

    last_vs_prev_pct = None
    if prev_val > 0:
        last_vs_prev_pct = (last_val / prev_val) - 1.0

    baseline_values = values[-(baseline_window + 1) : -1] if len(values) > MIN_BASELINE_POINTS else []
    baseline_mean = _mean(baseline_values) if baseline_values else None
    baseline_sd = _stddev(baseline_values) if baseline_values else None

    z = None
    ratio = None
    if baseline_mean is not None and baseline_mean >= min_baseline_mean and baseline_sd is not None:
        ratio = (last_val / baseline_mean) if baseline_mean > 0 else None
        z = (last_val - baseline_mean) / baseline_sd if baseline_sd > 0 else None

    return {
        'num_points': len(points),
        'last_bucket': {'label': last_label, 'count': last_val},
        'prev_bucket': {'label': prev_label, 'count': prev_val},
        'signals': {
            'last_vs_prev': {'abs': last_val - prev_val, 'pct': last_vs_prev_pct},
            'last_vs_baseline': {
                'baseline_window': baseline_window,
                'baseline_mean': baseline_mean,
                'baseline_sd': baseline_sd,
                'ratio': ratio,
                'z': z,
                'min_baseline_mean': min_baseline_mean,
            },
        },
    }


def _company_buckets_from_search(payload: Any) -> list[tuple[str, int]]:
    buckets = (payload or {}).get('aggregations', {}).get('company', {}).get('company', {}).get('buckets')
    if not isinstance(buckets, list):
        return []

    out: list[tuple[str, int]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        key = b.get('key')
        doc_count = b.get('doc_count')
        if not isinstance(key, str) or not isinstance(doc_count, int):
            continue
        out.append((key, doc_count))

    out.sort(key=lambda t: t[1], reverse=True)
    return out


async def geo_logic(**filters: Any) -> Any:
    """Execute a CFPB geo aggregation query."""
    params = build_params(**filters)
    return await _get_json(f'{BASE_URL}geo/states', params=params)


async def suggest_logic(field: Literal['company', 'zip_code'], text: str, size: int) -> Any:
    """Fetch autocomplete suggestions for company or zip_code."""
    params = {'text': text, 'size': size}
    endpoint = '_suggest_company' if field == 'company' else '_suggest_zip'
    data = await _get_json(f'{BASE_URL}{endpoint}', params=params)
    if isinstance(data, list):
        return data[:size]
    return data


async def document_logic(complaint_id: str) -> Any:
    """Fetch a single complaint document by its ID."""
    return await _get_json(f'{BASE_URL}{complaint_id}', params={})


def build_cfpb_ui_url(
    *,
    search_term: str | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    company: list[str] | None = None,
    product: list[str] | None = None,
    issue: list[str] | None = None,
    state: list[str] | None = None,
    has_narrative: str | None = None,
    company_response: list[str] | None = None,
    company_public_response: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    tags: list[str] | None = None,
    submitted_via: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
    tab: str | None = None,
    lens: str | None = None,
    sub_lens: str | None = None,
    chart_type: str | None = None,
    date_interval: str | None = None,
) -> str:
    """Build a URL to the official CFPB consumer complaints UI."""
    api_params: dict[str, Any] = {
        'search_term': search_term,
        'date_received_min': date_received_min,
        'date_received_max': date_received_max,
        'company': company,
        'product': product,
        'issue': issue,
        'state': state,
        'has_narrative': has_narrative,
        'company_response': company_response,
        'company_public_response': company_public_response,
        'consumer_disputed': consumer_disputed,
        'tags': tags,
        'submitted_via': submitted_via,
        'timely': timely,
        'zip_code': zip_code,
    }

    if lens:
        api_params['lens'] = lens
    if sub_lens:
        api_params['sub_lens'] = sub_lens
    if chart_type:
        api_params['chartType'] = chart_type
    if date_interval:
        api_params['trend_interval'] = date_interval.lower()

    return build_deeplink_url(api_params, tab=tab)


def generate_citations(
    *,
    context_type: Literal['search', 'trends', 'geo', 'suggest', 'document'],
    total_hits: int | None = None,
    complaint_id: str | None = None,
    lens: str | None = None,
    **params: Any,
) -> list[dict[str, str]]:
    """Generate citation URLs for MCP responses (Phase 4.6).

    Returns a list of citation objects with type, URL, and description.
    Smart tab selection based on context:
    - search → tab=List
    - trends → tab=Trends with lens/chartType
    - geo → tab=Map
    - document → direct link (if available)
    """
    citations: list[dict[str, str]] = []

    # Extract common filters from params
    filter_params = {
        k: v
        for k, v in params.items()
        if k
        in {
            'search_term',
            'date_received_min',
            'date_received_max',
            'company',
            'product',
            'issue',
            'state',
            'has_narrative',
            'company_response',
            'company_public_response',
            'consumer_disputed',
            'tags',
            'submitted_via',
            'timely',
            'zip_code',
        }
    }

    if context_type == 'search':
        # List view citation
        url = build_deeplink_url(filter_params, tab='List')
        desc = 'View these matching complaint(s) on CFPB.gov'
        if total_hits is not None and isinstance(total_hits, int):
            desc = f'View all {total_hits:,} matching complaint(s) on CFPB.gov'
        citations.append({'type': 'search_results', 'url': url, 'description': desc})

    elif context_type == 'trends':
        # Trends chart citation
        trend_params = {
            **filter_params,
            'lens': lens or 'Overview',
            'chartType': 'line',
            'trend_interval': 'month',
        }
        url = build_deeplink_url(trend_params, tab='Trends')
        citations.append(
            {
                'type': 'trends_chart',
                'url': url,
                'description': 'Interactive trends chart on CFPB.gov',
            }
        )

    elif context_type == 'geo':
        # Map view citation
        url = build_deeplink_url(filter_params, tab='Map')
        citations.append(
            {
                'type': 'geographic_map',
                'url': url,
                'description': 'Interactive geographic map on CFPB.gov',
            }
        )

    elif context_type == 'document' and complaint_id:
        # Individual complaint (List view is best we can do without complaint-specific URLs)
        base_url = 'https://www.consumerfinance.gov/data-research/consumer-complaints/search/'
        citations.append(
            {
                'type': 'complaint_detail',
                'url': f'{base_url}?tab=List',
                'description': f'Search for complaint {complaint_id} on CFPB.gov',
            }
        )

    # For all contexts except document-only, add a list view if not already present
    if context_type in {'trends', 'geo'} and filter_params:
        list_url = build_deeplink_url(filter_params, tab='List')
        citations.append(
            {
                'type': 'search_results',
                'url': list_url,
                'description': 'Browse matching complaints on CFPB.gov',
            }
        )

    return citations


async def screenshot_cfpb_ui(
    browser: Browser | None,
    url: str,
    *,
    wait_for_charts: bool = True,
    timeout: int = 30000,
) -> bytes:
    """Capture a screenshot of the official CFPB UI at the given URL.

    Returns PNG image bytes.
    Raises HTTPException(503) if Playwright is unavailable.
    """
    if browser is None:
        raise HTTPException(
            status_code=503,
            detail=SCREENSHOT_UNAVAILABLE_DETAIL,
        )

    context = await browser.new_context(
        viewport={'width': 890, 'height': 1080},
        user_agent=(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
    )

    try:
        page = await context.new_page()
        await page.goto(url, timeout=timeout, wait_until='networkidle')

        # If we expect charts, give D3/visualization time to render.
        if wait_for_charts:
            await page.wait_for_timeout(3000)

        # Hide the tour button that covers part of the legend
        with suppress(PlaywrightError, PlaywrightTimeoutError):
            await page.evaluate(
                """
                const tourButton = document.querySelector('button.tour-button');
                if (tourButton) {
                    tourButton.style.display = 'none';
                }
                """
            )

        # Debug: Save the page HTML to inspect structure
        if os.getenv('DEBUG_CFPB_UI'):
            html_content = await page.content()
            with tempfile.NamedTemporaryFile(prefix='cfpb_page_debug_', suffix='.html', delete=False) as tmp:
                debug_path = Path(tmp.name)

            debug_path.write_text(html_content, encoding='utf-8')
            print(f'[DEBUG] Saved page HTML to {debug_path}')

            def _schedule_debug_file_cleanup(path: Path, delay_seconds: float = 300.0) -> None:
                def _cleanup() -> None:
                    with suppress(OSError):
                        path.unlink()

                timer = threading.Timer(delay_seconds, _cleanup)
                timer.daemon = True
                timer.start()

            _schedule_debug_file_cleanup(debug_path)
        # Try multiple possible selectors for the chart area
        # The CFPB dashboard uses Britecharts D3 library
        chart_selectors = [
            '.layout-row:has(section.chart)',  # Parent div containing chart and legend
            'section.chart',  # The main chart section (fallback)
            '.chart-wrapper',  # Chart wrapper div
            '#line-chart',  # Line chart container
            '.trends-panel',  # The entire trends panel section (last resort)
        ]

        for selector in chart_selectors:
            try:
                chart_element = await page.query_selector(selector)
                if chart_element:
                    # Check if element is visible and has reasonable dimensions
                    box = await chart_element.bounding_box()
                    print(f"[DEBUG] Testing selector '{selector}': found={chart_element is not None}, box={box}")
                    if box and box['width'] > CHART_MIN_WIDTH and box['height'] > CHART_MIN_HEIGHT:
                        print(f'[DEBUG] ✓ Using chart selector: {selector}, size: {box["width"]}x{box["height"]}')
                        return await chart_element.screenshot(type='png')
                    if box:
                        print(f'[DEBUG] ✗ Element too small: {box["width"]}x{box["height"]}')
            except Exception as e:
                print(f'[DEBUG] Selector {selector} failed: {e}')
                continue

        # Fallback: Take full page screenshot
        print('[DEBUG] No suitable chart element found, taking full page screenshot')
        return await page.screenshot(type='png', full_page=True)

    finally:
        await context.close()


# -------------------------------------------------------------------------
# 3) Interface A: MCP Tools (for Claude Desktop)
# -------------------------------------------------------------------------


@server.tool()
async def search_complaints(
    search_term: str | None = None,
    field: SearchField = 'complaint_what_happened',
    size: int = 10,
    from_index: int = 0,
    sort: SearchSort = 'relevance_desc',
    search_after: str | None = None,
    no_highlight: bool = False,
    company: list[str] | None = None,
    company_public_response: list[str] | None = None,
    company_response: list[str] | None = None,
    consumer_consent_provided: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    company_received_min: str | None = None,
    company_received_max: str | None = None,
    has_narrative: list[str] | None = None,
    issue: list[str] | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    submitted_via: list[str] | None = None,
    tags: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
) -> Any:
    """Search the Consumer Complaint Database."""
    data = await search_logic(
        size=size,
        from_index=from_index,
        sort=sort,
        search_after=search_after,
        no_highlight=no_highlight,
        search_term=search_term,
        field=field,
        company=company,
        company_public_response=company_public_response,
        company_response=company_response,
        consumer_consent_provided=consumer_consent_provided,
        consumer_disputed=consumer_disputed,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company_received_min=company_received_min,
        company_received_max=company_received_max,
        has_narrative=has_narrative,
        issue=issue,
        product=product,
        state=state,
        submitted_via=submitted_via,
        tags=tags,
        timely=timely,
        zip_code=zip_code,
    )

    # Phase 4.6: Add citation URLs
    total_hits = data.get('hits', {}).get('total') if isinstance(data, dict) else None
    citations = generate_citations(
        context_type='search',
        total_hits=total_hits,
        search_term=search_term,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company=company,
        product=product,
        issue=issue,
        state=state,
        has_narrative=has_narrative[0] if has_narrative else None,
        company_response=company_response,
        company_public_response=company_public_response,
        consumer_disputed=consumer_disputed,
        tags=tags,
        submitted_via=submitted_via,
        timely=timely,
        zip_code=zip_code,
    )

    return {'data': data, 'citations': citations}


@server.tool()
async def list_complaint_trends(
    lens: str = 'overview',
    trend_interval: str = 'month',
    trend_depth: int = 5,
    sub_lens: str | None = None,
    sub_lens_depth: int = 5,
    focus: str | None = None,
    search_term: str | None = None,
    field: SearchField = 'complaint_what_happened',
    company: list[str] | None = None,
    company_public_response: list[str] | None = None,
    company_response: list[str] | None = None,
    consumer_consent_provided: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    company_received_min: str | None = None,
    company_received_max: str | None = None,
    has_narrative: list[str] | None = None,
    issue: list[str] | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    submitted_via: list[str] | None = None,
    tags: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
) -> Any:
    """Get aggregated trend data for complaints over time."""
    data = await trends_logic(
        lens,
        trend_interval,
        trend_depth,
        sub_lens,
        sub_lens_depth,
        focus,
        search_term=search_term,
        field=field,
        company=company,
        company_public_response=company_public_response,
        company_response=company_response,
        consumer_consent_provided=consumer_consent_provided,
        consumer_disputed=consumer_disputed,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company_received_min=company_received_min,
        company_received_max=company_received_max,
        has_narrative=has_narrative,
        issue=issue,
        product=product,
        state=state,
        submitted_via=submitted_via,
        tags=tags,
        timely=timely,
        zip_code=zip_code,
    )

    # Phase 4.6: Add citation URLs
    citations = generate_citations(
        context_type='trends',
        lens=lens,
        search_term=search_term,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company=company,
        product=product,
        issue=issue,
        state=state,
        has_narrative=has_narrative[0] if has_narrative else None,
        company_response=company_response,
        company_public_response=company_public_response,
        consumer_disputed=consumer_disputed,
        tags=tags,
        submitted_via=submitted_via,
        timely=timely,
        zip_code=zip_code,
    )

    return {'data': data, 'citations': citations}


@server.tool()
async def get_state_aggregations(
    search_term: str | None = None,
    field: SearchField = 'complaint_what_happened',
    company: list[str] | None = None,
    company_public_response: list[str] | None = None,
    company_response: list[str] | None = None,
    consumer_consent_provided: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    company_received_min: str | None = None,
    company_received_max: str | None = None,
    has_narrative: list[str] | None = None,
    issue: list[str] | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    submitted_via: list[str] | None = None,
    tags: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
) -> Any:
    """Get complaint counts aggregated by US State."""
    data = await geo_logic(
        search_term=search_term,
        field=field,
        company=company,
        company_public_response=company_public_response,
        company_response=company_response,
        consumer_consent_provided=consumer_consent_provided,
        consumer_disputed=consumer_disputed,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company_received_min=company_received_min,
        company_received_max=company_received_max,
        has_narrative=has_narrative,
        issue=issue,
        product=product,
        state=state,
        submitted_via=submitted_via,
        tags=tags,
        timely=timely,
        zip_code=zip_code,
    )

    # Phase 4.6: Add citation URLs
    citations = generate_citations(
        context_type='geo',
        search_term=search_term,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company=company,
        product=product,
        issue=issue,
        state=state,
        has_narrative=has_narrative[0] if has_narrative else None,
        company_response=company_response,
        company_public_response=company_public_response,
        consumer_disputed=consumer_disputed,
        tags=tags,
        submitted_via=submitted_via,
        timely=timely,
        zip_code=zip_code,
    )

    return {'data': data, 'citations': citations}


@server.tool()
async def get_complaint_document(complaint_id: str) -> Any:
    """Retrieve a single complaint by its ID."""
    return await document_logic(complaint_id)


@server.tool()
async def suggest_filter_values(
    field: Literal['company', 'zip_code'],
    text: str,
    size: int = 10,
) -> Any:
    """Autocomplete helper for filter values (company or zip_code)."""
    return await suggest_logic(field, text, size)


@server.tool()
async def generate_cfpb_dashboard_url(
    search_term: str | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    company: list[str] | None = None,
    product: list[str] | None = None,
    issue: list[str] | None = None,
    state: list[str] | None = None,
    has_narrative: str | None = None,
    company_response: list[str] | None = None,
) -> str:
    """Generate a deep-link URL to the official CFPB consumer complaints dashboard.

    This creates a URL pre-configured with filters matching your search criteria.
    Users can click the link to explore the official government visualization tool
    with charts, trends, and interactive data exploration.

    Perfect for:
    - Sharing pre-filtered complaint views
    - Providing authoritative, branded visualizations
    - Giving users access to the full official dashboard
    """
    return build_cfpb_ui_url(
        search_term=search_term,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company=company,
        product=product,
        issue=issue,
        state=state,
        has_narrative=has_narrative,
        company_response=company_response,
    )


@server.tool()
async def capture_cfpb_chart_screenshot(
    search_term: str | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    product: list[str] | None = None,
    issue: list[str] | None = None,
    state: list[str] | None = None,
    company: list[str] | None = None,
    lens: str = 'Product',
    chart_type: str = 'line',
    date_interval: str = 'Month',
) -> str:
    """Capture a screenshot of the official CFPB trends chart as a PNG image."""
    if not getattr(app.state, 'browser', None):
        raise HTTPException(status_code=503, detail=SCREENSHOT_UNAVAILABLE_DETAIL)

    api_params: dict[str, Any] = {
        'lens': lens,
        'chartType': chart_type,
        'trend_interval': date_interval.lower(),
        'search_term': search_term,
        'date_received_min': date_received_min,
        'date_received_max': date_received_max,
        'product': product,
        'issue': issue,
        'state': state,
        'company': company,
    }
    url = build_deeplink_url(api_params, tab='Trends')

    screenshot_bytes = await screenshot_cfpb_ui(
        app.state.browser,
        url,
        wait_for_charts=True,
    )

    return base64.b64encode(screenshot_bytes).decode('utf-8')


@server.tool()
async def get_overall_trend_signals(
    lens: str = 'overview',
    trend_interval: str = 'month',
    trend_depth: int = 24,
    baseline_window: int = 8,
    min_baseline_mean: float = 10.0,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    search_term: str | None = None,
    field: SearchField = 'complaint_what_happened',
    company: list[str] | None = None,
    company_public_response: list[str] | None = None,
    company_response: list[str] | None = None,
    consumer_consent_provided: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    company_received_min: str | None = None,
    company_received_max: str | None = None,
    has_narrative: list[str] | None = None,
    issue: list[str] | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    submitted_via: list[str] | None = None,
    tags: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
) -> Any:
    """Compute simple spike/velocity signals from upstream overall trends buckets."""
    payload = await trends_logic(
        lens,
        trend_interval,
        trend_depth,
        None,
        0,
        None,
        search_term=search_term,
        field=field,
        company=company,
        company_public_response=company_public_response,
        company_response=company_response,
        consumer_consent_provided=consumer_consent_provided,
        consumer_disputed=consumer_disputed,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company_received_min=company_received_min,
        company_received_max=company_received_max,
        has_narrative=has_narrative,
        issue=issue,
        product=product,
        state=state,
        submitted_via=submitted_via,
        tags=tags,
        timely=timely,
        zip_code=zip_code,
    )
    points = _drop_current_month(_extract_overall_points(payload))
    return {
        'params': {
            'lens': lens,
            'trend_interval': trend_interval,
            'trend_depth': trend_depth,
            'date_received_min': date_received_min,
            'date_received_max': date_received_max,
        },
        'signals': {
            'overall': _compute_simple_signals(
                points,
                baseline_window=baseline_window,
                min_baseline_mean=min_baseline_mean,
            )
        },
    }


@server.tool()
async def rank_group_spikes(
    group: Literal['product', 'issue'],
    lens: str = 'overview',
    trend_interval: str = 'month',
    trend_depth: int = 12,
    sub_lens_depth: int = 10,
    top_n: int = 10,
    baseline_window: int = 8,
    min_baseline_mean: float = 10.0,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    search_term: str | None = None,
    field: SearchField = 'complaint_what_happened',
    company: list[str] | None = None,
    company_public_response: list[str] | None = None,
    company_response: list[str] | None = None,
    consumer_consent_provided: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    company_received_min: str | None = None,
    company_received_max: str | None = None,
    has_narrative: list[str] | None = None,
    issue: list[str] | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    submitted_via: list[str] | None = None,
    tags: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
) -> Any:
    """Rank group values (e.g., products or issues) by latest-bucket spike."""
    payload = await trends_logic(
        lens,
        trend_interval,
        trend_depth,
        group,
        sub_lens_depth,
        None,
        search_term=search_term,
        field=field,
        company=company,
        company_public_response=company_public_response,
        company_response=company_response,
        consumer_consent_provided=consumer_consent_provided,
        consumer_disputed=consumer_disputed,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company_received_min=company_received_min,
        company_received_max=company_received_max,
        has_narrative=has_narrative,
        issue=issue,
        product=product,
        state=state,
        submitted_via=submitted_via,
        tags=tags,
        timely=timely,
        zip_code=zip_code,
    )

    series = _extract_group_series(payload, group)
    scored: list[dict[str, Any]] = []
    for s in series:
        points = _drop_current_month(s.get('points') or [])
        signals = _compute_simple_signals(points, baseline_window=baseline_window, min_baseline_mean=min_baseline_mean)
        if 'error' in signals:
            continue
        scored.append(
            {
                'group': s.get('group'),
                'doc_count': s.get('doc_count'),
                **signals,
            }
        )

    scored.sort(
        key=lambda r: (
            (r.get('signals', {}).get('last_vs_baseline', {}).get('z') is None),
            r.get('signals', {}).get('last_vs_baseline', {}).get('z') or float('-inf'),
        ),
        reverse=True,
    )

    return {
        'params': {
            'group': group,
            'lens': lens,
            'trend_interval': trend_interval,
            'trend_depth': trend_depth,
            'sub_lens_depth': sub_lens_depth,
            'top_n': top_n,
            'date_received_min': date_received_min,
            'date_received_max': date_received_max,
        },
        'results': scored[:top_n],
    }


@server.tool()
async def rank_company_spikes(
    lens: str = 'overview',
    trend_interval: str = 'month',
    trend_depth: int = 12,
    top_n: int = 10,
    baseline_window: int = 8,
    min_baseline_mean: float = 25.0,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    search_term: str | None = None,
    field: SearchField = 'complaint_what_happened',
    company_public_response: list[str] | None = None,
    company_response: list[str] | None = None,
    consumer_consent_provided: list[str] | None = None,
    consumer_disputed: list[str] | None = None,
    company_received_min: str | None = None,
    company_received_max: str | None = None,
    has_narrative: list[str] | None = None,
    issue: list[str] | None = None,
    product: list[str] | None = None,
    state: list[str] | None = None,
    submitted_via: list[str] | None = None,
    tags: list[str] | None = None,
    timely: list[str] | None = None,
    zip_code: list[str] | None = None,
) -> Any:
    """Pipeline-style company spikes: search aggs -> top companies -> trends per company -> rank."""
    search_payload = await search_logic(
        size=0,
        from_index=0,
        sort='created_date_desc',
        search_after=None,
        no_highlight=True,
        search_term=search_term,
        field=field,
        company=None,
        company_public_response=company_public_response,
        company_response=company_response,
        consumer_consent_provided=consumer_consent_provided,
        consumer_disputed=consumer_disputed,
        date_received_min=date_received_min,
        date_received_max=date_received_max,
        company_received_min=company_received_min,
        company_received_max=company_received_max,
        has_narrative=has_narrative,
        issue=issue,
        product=product,
        state=state,
        submitted_via=submitted_via,
        tags=tags,
        timely=timely,
        zip_code=zip_code,
    )

    top_companies = _company_buckets_from_search(search_payload)[:top_n]
    results: list[dict[str, Any]] = []
    for company, company_doc_count in top_companies:
        trends_payload = await trends_logic(
            lens,
            trend_interval,
            trend_depth,
            None,
            0,
            None,
            search_term=search_term,
            field=field,
            company=[company],
            company_public_response=company_public_response,
            company_response=company_response,
            consumer_consent_provided=consumer_consent_provided,
            consumer_disputed=consumer_disputed,
            date_received_min=date_received_min,
            date_received_max=date_received_max,
            company_received_min=company_received_min,
            company_received_max=company_received_max,
            has_narrative=has_narrative,
            issue=issue,
            product=product,
            state=state,
            submitted_via=submitted_via,
            tags=tags,
            timely=timely,
            zip_code=zip_code,
        )
        points = _drop_current_month(_extract_overall_points(trends_payload))
        signals = _compute_simple_signals(points, baseline_window=baseline_window, min_baseline_mean=min_baseline_mean)
        results.append(
            {
                'company': company,
                'company_doc_count': company_doc_count,
                'computed': signals,
            }
        )

    results.sort(
        key=lambda r: (
            (r.get('computed', {}).get('signals', {}).get('last_vs_baseline', {}).get('z') is None),
            r.get('computed', {}).get('signals', {}).get('last_vs_baseline', {}).get('z') or float('-inf'),
        ),
        reverse=True,
    )

    return {
        'date_filters': {
            'date_received_min': date_received_min,
            'date_received_max': date_received_max,
        },
        'ranking': 'last bucket vs baseline z-score',
        'results': results,
    }


# -------------------------------------------------------------------------
# 4) Application Mount
# -------------------------------------------------------------------------

# Phase 5.3: Streamable HTTP Only
# We explicitly route /mcp to avoid Starlette's automatic 307 redirects
# that occur when using app.mount("/mcp", ...) for the root path.

_http_app = server.streamable_http_app()


async def mcp_http(request: Request) -> Response:
    """Proxy requests into the FastMCP streamable HTTP app."""
    body = await request.body()
    scope = request.scope
    status_code: int | None = None
    response_headers: list[tuple[bytes, bytes]] = []
    chunks: list[bytes] = []
    sent_body = False

    async def receive() -> Message:
        nonlocal sent_body
        if sent_body:
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        sent_body = True
        return {'type': 'http.request', 'body': body, 'more_body': False}

    async def send(message: Message) -> None:
        nonlocal status_code, response_headers
        msg_type = message.get('type')
        if msg_type == 'http.response.start':
            status_code = int(message.get('status', 200))
            raw = message.get('headers', [])
            if isinstance(raw, list):
                response_headers = [(bytes(k), bytes(v)) for k, v in raw]
        elif msg_type == 'http.response.body':
            body_part = message.get('body', b'')
            if isinstance(body_part, bytes | bytearray):
                chunks.append(bytes(body_part))

    await _http_app(scope, receive, send)

    return Response(
        content=b''.join(chunks),
        status_code=status_code or 200,
        headers={k.decode('latin-1'): v.decode('latin-1') for k, v in response_headers},
    )


# Streamable HTTP: POST /mcp
app.add_api_route('/mcp', mcp_http, methods=['POST'], include_in_schema=False)


@app.get('/', include_in_schema=False)
async def root() -> dict[str, Any]:
    """Return a minimal health payload."""
    return {
        'name': 'cfpb-mcp',
        'message': 'CFPB MCP server is running (dev update 2).',
        'mcp': {
            'http': '/mcp',
        },
    }


if __name__ == '__main__':
    host = os.getenv('CFPB_MCP_HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run(app, host=host, port=port)
