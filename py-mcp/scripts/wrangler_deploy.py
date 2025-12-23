"""Load .env (if present) and run wrangler deploy with those environment vars."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print('python-dotenv is required to load .env (try: uv sync --dev).', file=sys.stderr)
        return

    env_path = Path(__file__).resolve().parents[1] / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def main() -> int:
    _load_dotenv()
    if not os.getenv('CLOUDFLARE_API_TOKEN'):
        print('CLOUDFLARE_API_TOKEN is not set (check your .env).', file=sys.stderr)
        return 1
    return subprocess.call(['npx', 'wrangler', 'deploy'])


if __name__ == '__main__':
    raise SystemExit(main())
