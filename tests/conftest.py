import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import closing
from typing import Iterator
from urllib.parse import urlparse

import httpx
import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:  # noqa: ARG001
    """Apply suite markers based on file path.

    - tests/e2e/** -> e2e
    - tests/unit/** -> unit
    - everything else under tests/** -> integration

    This keeps suite selection stable even as the server is refactored.
    """

    for item in items:
        path = str(getattr(item, "fspath", ""))
        normalized = path.replace("\\", "/")

        if "/tests/e2e/" in normalized:
            item.add_marker(pytest.mark.e2e)
        elif "/tests/unit/" in normalized:
            item.add_marker(pytest.mark.unit)
        elif "/tests/" in normalized:
            item.add_marker(pytest.mark.integration)


def _pick_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _is_server_ready(url: str, *, require_paths: list[str] | None = None) -> bool:
    try:
        r = httpx.get(f"{url}/openapi.json", timeout=5)
        if r.status_code != 200:
            return False
        if not require_paths:
            return True

        spec = r.json()
        paths = spec.get("paths") if isinstance(spec, dict) else None
        if not isinstance(paths, dict):
            return False
        return all(p in paths for p in require_paths)
    except Exception:  # noqa: BLE001
        return False


def _parse_host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported scheme in TEST_SERVER_URL: {url}")
    if not parsed.hostname or parsed.port is None:
        raise ValueError(f"TEST_SERVER_URL must include hostname and port: {url}")
    return str(parsed.hostname), int(parsed.port)


@pytest.fixture(scope="session")
def server_url() -> Iterator[str]:
    """Start uvicorn in a subprocess and return the base URL."""

    configured_url = os.environ.get("TEST_SERVER_URL")
    if configured_url:
        url = configured_url.rstrip("/")
        # If a server is already running there *and* matches our current contract, reuse it.
        required_paths = [
            "/signals/overall",
            "/signals/group",
            "/signals/company",
            "/cfpb-ui/url",
            "/cfpb-ui/screenshot",
        ]
        if _is_server_ready(url, require_paths=required_paths):
            yield url
            return

        # If the server is running but doesn't match the current contract, fall back to
        # starting a subprocess server on a free port so integration tests validate
        # the checked-out code rather than an older external process.
        if _is_server_ready(url):
            configured_url = None

        # If it's not running, only auto-start when it's a local address we can bind.
        if configured_url:
            host, port = _parse_host_port(url)
            if host not in {"127.0.0.1", "localhost"}:
                raise RuntimeError(
                    f"TEST_SERVER_URL was set to {url} but it is not reachable, and the host is not local; "
                    "refusing to auto-start uvicorn."
                )
    else:
        port = _pick_free_port()
        host = "127.0.0.1"
        url = f"http://{host}:{port}"

    if not configured_url:
        port = _pick_free_port()
        host = "127.0.0.1"
        url = f"http://{host}:{port}"

    env = os.environ.copy()
    # Avoid picking up a user-configured port
    env.pop("PORT", None)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server:app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.time() + 20
    last_err: Exception | None = None
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                if _is_server_ready(url):
                    break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
            time.sleep(0.2)

        if proc.poll() is not None:
            output = ""
            if proc.stdout is not None:
                output = proc.stdout.read() or ""
            raise RuntimeError(
                f"Server process exited early while starting on {url}. Last error: {last_err}.\nProcess output:\n{output}"
            )

        # Final readiness check
        if not _is_server_ready(url):
            raise RuntimeError(
                f"Server failed to become ready on {url}. Last error: {last_err}."
            )

        yield url
    finally:
        # If TEST_SERVER_URL was provided and already running, we returned early above.
        # Any server subprocess created here should be terminated.
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


@pytest.fixture()
def client(server_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=server_url, timeout=30) as c:
        yield c
