import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError(f'Server not ready on {host}:{port}')


@pytest.fixture(scope='module')
def server_url() -> Iterator[str]:
    host = '127.0.0.1'
    port = _free_port()
    env = os.environ.copy()
    env['FAST_MCP_HOST'] = host
    env['FAST_MCP_PORT'] = str(port)

    process = subprocess.Popen(
        [sys.executable, '-u', 'sidequest/notes_app.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(host, port)
    except Exception:
        stdout, stderr = process.communicate(timeout=5)
        raise RuntimeError(f'FastMCP notes app failed to start.\nstdout:\n{stdout}\nstderr:\n{stderr}') from None

    yield f'http://{host}:{port}'

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.mark.anyio
async def test_mounted_streamable_http(server_url: str) -> None:
    mcp_url = f'{server_url}/mcp'
    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as mcp:
            await mcp.initialize()
            result = await mcp.call_tool('calculate', {'a': 10, 'b': 20})
    payload = result.structuredContent or result.content
    if isinstance(payload, int):
        assert payload == 30
        return
    if isinstance(payload, dict):
        if 'result' in payload:
            assert payload['result'] == 30
            return
        if 'data' in payload:
            assert payload['data'] == 30
            return
    if isinstance(payload, list) and payload:
        text = getattr(payload[0], 'text', None)
        assert text == '30'
        return
    raise AssertionError(f'Unexpected payload shape: {payload!r}')
