"""Small probe for the public CFPB CCDB5 API.

Writes response payloads and a quick schema/shape summary into temp/output/.

Usage:
  uv run python temp/cfpb_api_probe.py --out temp/output

Notes:
- Keep terminal output tiny; inspect saved files instead.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

BASE_URL = (
    "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
)


@dataclass(frozen=True)
class ProbeResult:
    name: str
    url: str
    params: Dict[str, Any]
    status_code: int
    payload: Any


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _safe_key_summary(obj: Any, *, max_items: int = 30) -> Dict[str, Any]:
    """Produce a small, readable summary of an arbitrary JSON-ish payload."""

    def summarize(value: Any, depth: int = 0) -> Any:
        if depth >= 3:
            return {"type": type(value).__name__}
        if isinstance(value, dict):
            keys = list(value.keys())
            preview = keys[:max_items]
            return {
                "type": "dict",
                "keys": preview,
                "num_keys": len(keys),
                "examples": {
                    k: summarize(value[k], depth + 1)
                    for k in preview[: min(10, len(preview))]
                },
            }
        if isinstance(value, list):
            return {
                "type": "list",
                "len": len(value),
                "item_type": type(value[0]).__name__ if value else None,
                "first_item": summarize(value[0], depth + 1) if value else None,
            }
        return {"type": type(value).__name__, "value_preview": str(value)[:120]}

    return summarize(obj)


def _get(client: httpx.Client, path: str, *, params: Dict[str, Any]) -> ProbeResult:
    url = f"{BASE_URL}{path}" if not path.startswith("http") else path
    resp = client.get(url, params=params)
    payload: Any
    try:
        payload = resp.json()
    except Exception:
        payload = {"non_json_body": resp.text[:2000]}

    return ProbeResult(
        name=path,
        url=str(resp.url),
        params=params,
        status_code=resp.status_code,
        payload=payload,
    )


def run_probe(out_root: Path) -> Path:
    run_dir = out_root / f"probe_{_utc_stamp()}"
    _ensure_dir(run_dir)

    timeout = httpx.Timeout(30.0)
    headers = {"User-Agent": "cfpb-mcp-temp-probe/0.1"}

    results: List[ProbeResult] = []
    with httpx.Client(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        # Minimal search probe
        results.append(
            _get(
                client,
                "",
                params={
                    "size": 1,
                    "frm": 0,
                    "sort": "created_date_desc",
                    "no_highlight": True,
                    "no_aggs": True,
                },
            )
        )

        # Trends probe: overall volume over time
        results.append(
            _get(
                client,
                "trends",
                params={
                    "lens": "overview",
                    "trend_interval": "month",
                    "trend_depth": 24,
                },
            )
        )

        # Suggest company probe: should return a short list
        results.append(
            _get(client, "_suggest_company", params={"text": "bank", "size": 10})
        )

    manifest: Dict[str, Any] = {
        "base_url": BASE_URL,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "probes": [],
    }

    for idx, r in enumerate(results, start=1):
        slug = f"{idx:02d}_{r.name.replace('/', '_') or 'search'}"
        raw_path = run_dir / f"{slug}.raw.json"
        summary_path = run_dir / f"{slug}.summary.json"

        _write_json(
            raw_path,
            {
                "name": r.name,
                "url": r.url,
                "params": r.params,
                "status_code": r.status_code,
                "payload": r.payload,
            },
        )
        _write_json(summary_path, _safe_key_summary(r.payload))

        manifest["probes"].append(
            {
                "name": r.name,
                "url": r.url,
                "status_code": r.status_code,
                "raw_file": raw_path.name,
                "summary_file": summary_path.name,
            }
        )

    _write_json(run_dir / "manifest.json", manifest)

    readme = (
        "CFPB API probe outputs\n"
        "======================\n\n"
        "Files:\n"
        "- manifest.json: index of requests\n"
        "- *.raw.json: full response payloads\n"
        "- *.summary.json: small schema/shape summaries\n"
    )
    (run_dir / "README.txt").write_text(readme, encoding="utf-8")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="temp/output",
        help="Output root directory (default: temp/output)",
    )
    args = parser.parse_args()

    out_root = Path(args.out).resolve()
    _ensure_dir(out_root)

    run_dir = run_probe(out_root)
    # Minimal terminal output (user asked to prefer file outputs)
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
