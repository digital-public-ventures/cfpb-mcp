import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing

import httpx
import pytest

pytest.skip('Bearer auth not implemented; OAuth support planned.', allow_module_level=True)


def _dev_testing_api_key() -> str:
    # Local convenience: if a developer has set DEV_TESTING_API_KEY in their .env,
    # reuse it for authenticated smoke tests. CI should remain deterministic.
    return (os.getenv('DEV_TESTING_API_KEY') or 'test-key').strip() or 'test-key'


def _pick_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _is_server_ready(url: str) -> bool:
    try:
        r = httpx.get(f'{url}/', timeout=5)
        if r.status_code != 200:
            return False
        payload = r.json()
        return isinstance(payload, dict) and 'mcp' in payload
    except Exception:
        return False


def _start_server(*, env_overrides: dict[str, str]) -> tuple[subprocess.Popen[str], str]:
    port = _pick_free_port()
    host = '127.0.0.1'
    url = f'http://{host}:{port}'

    env = os.environ.copy()
    env.pop('PORT', None)
    env.update(env_overrides)

    proc: subprocess.Popen[str] = subprocess.Popen(
        [
            sys.executable,
            '-m',
            'uvicorn',
            'src.server:app',
            '--host',
            host,
            '--port',
            str(port),
            '--log-level',
            'warning',
        ],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.time() + 20
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if _is_server_ready(url):
                return proc, url
            time.sleep(0.2)

        output = ''
        if proc.stdout is not None:
            output = proc.stdout.read() or ''
        raise RuntimeError(f'Auth test server failed to start on {url}. Output:\n{output}')
    except Exception:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        raise


@pytest.fixture(scope='module')
def auth_server_url() -> Iterator[str]:
    key = _dev_testing_api_key()
    proc, url = _start_server(env_overrides={'CFPB_MCP_API_KEYS': key})
    try:
        yield url
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


@pytest.fixture(scope='module')
def rate_limited_auth_server_url() -> Iterator[str]:
    key = _dev_testing_api_key()
    proc, url = _start_server(
        env_overrides={
            'CFPB_MCP_API_KEYS': key,
            'CFPB_MCP_RATE_LIMIT_RPS': '0.000001',
            'CFPB_MCP_RATE_LIMIT_BURST': '1',
        }
    )
    try:
        yield url
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def test_mcp_http_requires_api_key(auth_server_url: str) -> None:
    with httpx.Client(timeout=5) as client:
        r = client.post(f'{auth_server_url}/mcp', json={})
        assert r.status_code == 401
        assert (r.headers.get('content-type') or '').startswith('application/json')


def test_mcp_http_allows_valid_api_key(auth_server_url: str) -> None:
    key = _dev_testing_api_key()
    with httpx.Client(timeout=5) as client:
        # We don't need to stream here, just check that the POST request gets through auth.
        # It might return 200, 400 (bad JSON-RPC), or 406 (Not Acceptable),
        # but 401 means auth failed.
        r = client.post(
            f'{auth_server_url}/mcp',
            headers={'X-API-Key': key, 'Accept': 'application/json'},
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
        )
        assert r.status_code != 401


def test_mcp_rate_limit_429(rate_limited_auth_server_url: str) -> None:
    key = _dev_testing_api_key()
    with httpx.Client(timeout=5) as client:
        r1 = client.post(
            f'{rate_limited_auth_server_url}/mcp',
            headers={'X-API-Key': key},
            json={},
        )
        assert r1.status_code != 401
        assert r1.status_code != 429

        r2 = client.post(
            f'{rate_limited_auth_server_url}/mcp',
            headers={'X-API-Key': key},
            json={},
        )
        assert r2.status_code == 429
