import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import pytest
from fastmcp import Client


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
    env['FAST_MCP_PATH'] = '/mcp'

    process = subprocess.Popen(
        [sys.executable, '-u', 'sidequest/server.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(host, port)
    except Exception:
        stdout, stderr = process.communicate(timeout=5)
        raise RuntimeError(f'FastMCP server failed to start.\nstdout:\n{stdout}\nstderr:\n{stderr}') from None

    yield f'http://{host}:{port}/mcp'

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.mark.anyio
async def test_demo_server_add(server_url: str) -> None:
    async with Client(server_url) as client:
        result = await client.call_tool('add', {'a': 2, 'b': 3})
    assert result.data == 5
