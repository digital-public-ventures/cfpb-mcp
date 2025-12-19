from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from shutil import which
from typing import Optional


@dataclass(frozen=True)
class TunnelInfo:
    public_url: str
    proto: str


def _is_process_alive(proc: subprocess.Popen[str]) -> bool:
    return proc.poll() is None


def _terminate_process(
    proc: subprocess.Popen[str], *, name: str, timeout_s: float = 5.0
) -> None:
    if not _is_process_alive(proc):
        return

    try:
        proc.terminate()
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    try:
        proc.kill()
    except Exception:
        pass


def _poll_http_json(url: str, *, timeout_s: float) -> Optional[dict]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            time.sleep(0.2)
    return None


def _wait_for_server_ready(base_url: str, *, timeout_s: float) -> None:
    url = f"{base_url.rstrip('/')}/openapi.json"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if 200 <= resp.status < 300:
                    return
        except urllib.error.URLError:
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready at {url} within {timeout_s:.1f}s")


def _wait_for_ngrok_tunnel(*, timeout_s: float) -> TunnelInfo:
    # ngrok's local introspection API is typically available on 127.0.0.1:4040
    data = _poll_http_json("http://127.0.0.1:4040/api/tunnels", timeout_s=timeout_s)
    if not data:
        raise RuntimeError(
            "ngrok did not expose a tunnel via http://127.0.0.1:4040/api/tunnels"
        )

    tunnels = data.get("tunnels")
    if not isinstance(tunnels, list) or not tunnels:
        raise RuntimeError("ngrok tunnel list was empty")

    # Prefer https tunnel if available.
    https = next(
        (t for t in tunnels if t.get("proto") == "https" and t.get("public_url")), None
    )
    chosen = https or next(
        (t for t in tunnels if t.get("public_url") and t.get("proto")), None
    )
    if not chosen:
        raise RuntimeError("ngrok returned tunnels but none had a public_url")

    return TunnelInfo(public_url=str(chosen["public_url"]), proto=str(chosen["proto"]))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run the FastAPI server and ngrok together for local development.",
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "127.0.0.1"),
        help="Local bind host for the FastAPI server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--ngrok-region",
        default=os.environ.get("NGROK_REGION"),
        help="Optional ngrok region (e.g. us, eu, ap).",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=float(os.environ.get("STARTUP_TIMEOUT", "30")),
        help="Seconds to wait for server and ngrok to become ready.",
    )

    args = parser.parse_args(argv)

    if which("ngrok") is None:
        raise SystemExit(
            "ngrok is not installed or not on PATH.\n\n"
            "Install it first (https://ngrok.com/download), then run:\n"
            "  ngrok config add-authtoken <YOUR_TOKEN>\n"
        )

    base_url = f"http://{args.host}:{args.port}"

    server_cmd = ["uv", "run", "python", "server.py"]
    ngrok_cmd = ["ngrok", "http", str(args.port), "--log", "stdout"]
    if args.ngrok_region:
        ngrok_cmd.extend(["--region", args.ngrok_region])

    server_proc: Optional[subprocess.Popen[str]] = None
    ngrok_proc: Optional[subprocess.Popen[str]] = None

    def _shutdown(*_sig: object) -> None:
        if ngrok_proc is not None:
            _terminate_process(ngrok_proc, name="ngrok")
        if server_proc is not None:
            _terminate_process(server_proc, name="server")

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server_proc = subprocess.Popen(server_cmd, text=True)
        _wait_for_server_ready(base_url, timeout_s=args.startup_timeout)

        ngrok_proc = subprocess.Popen(ngrok_cmd, text=True)
        tunnel = _wait_for_ngrok_tunnel(timeout_s=args.startup_timeout)

        print("\nLocal server:")
        print(f"  {base_url}")
        print(f"  OpenAPI: {base_url}/openapi.json")
        print(f"  MCP SSE: {base_url}/mcp/sse")
        print("\nPublic ngrok URL:")
        print(f"  {tunnel.public_url}")
        print(f"  OpenAPI: {tunnel.public_url}/openapi.json")
        print("\nPress Ctrl+C to stop.\n")

        while True:
            assert server_proc is not None
            assert ngrok_proc is not None
            if server_proc.poll() is not None:
                raise RuntimeError(f"Server exited with code {server_proc.returncode}")
            if ngrok_proc.poll() is not None:
                raise RuntimeError(f"ngrok exited with code {ngrok_proc.returncode}")
            time.sleep(0.5)

    finally:
        _shutdown()


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130)
