import argparse
import os
import sys
from typing import NoReturn

import pytest


def _die(message: str, code: int = 2) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def _pytest(args: list[str], *, extra_env: dict[str, str] | None = None) -> int:
    if extra_env:
        os.environ.update(extra_env)

    # Ensure the repository root is the working directory and on sys.path.
    # When this script is executed as `python scripts/run_tests.py`, Python sets
    # sys.path[0] to the scripts/ directory, which can break imports like `import server`.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    return int(pytest.main(args))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run pytest suites for this repo (unit/integration/e2e/full)."
    )
    parser.add_argument(
        "suite",
        nargs="?",
        default="integration",
        choices=["unit", "integration", "e2e", "full"],
        help="Which suite to run (default: integration)",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional args to pass to pytest (prefix with '--', e.g. -- -q -k search)",
    )

    ns = parser.parse_args()

    extra = [a for a in ns.pytest_args if a != "--"]

    # Default to concise output unless user overrides.
    default_args: list[str] = []
    if not any(a in extra for a in ["-q", "-v"]):
        default_args = ["-q"]

    if ns.suite == "unit":
        return _pytest(default_args + ["-m", "unit"] + extra)

    if ns.suite == "integration":
        # Includes anything under tests/ except e2e/unit.
        return _pytest(default_args + ["-m", "integration"] + extra)

    if ns.suite == "e2e":
        # E2E tests are opt-in and may require provider keys.
        env = {"RUN_E2E": os.getenv("RUN_E2E", "1")}
        return _pytest(default_args + ["-m", "e2e", "-rs"] + extra, extra_env=env)

    if ns.suite == "full":
        # Run unit, then integration, then e2e.
        rc = _pytest(default_args + ["-m", "unit"] + extra)
        if rc != 0:
            return rc

        rc = _pytest(default_args + ["-m", "integration"] + extra)
        if rc != 0:
            return rc
        env = {"RUN_E2E": os.getenv("RUN_E2E", "1")}
        return _pytest(default_args + ["-m", "e2e", "-rs"] + extra, extra_env=env)

    _die(f"Unknown suite: {ns.suite}")


if __name__ == "__main__":
    raise SystemExit(main())
