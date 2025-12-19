"""Explore what 'signal helpers (proxy-based)' could mean using upstream CFPB trends.

This script:
- Calls the public CFPB CCDB5 trends endpoint for a few scenarios
- Computes simple, auditable spike/velocity-style signals
- Writes raw upstream payloads + computed summaries to temp/output/

Usage:
  uv run python temp/signal_helpers_explore.py --out temp/output

Design goals:
- Prefer saved outputs over terminal output.
- Keep heuristics simple and explainable (baseline windows, minimum counts).
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

BASE_URL = (
    "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _prune_params(params: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        if isinstance(v, list):
            vv = [
                x
                for x in v
                if x is not None and (not isinstance(x, str) or x.strip() != "")
            ]
            if not vv:
                continue
            cleaned[k] = vv
            continue
        cleaned[k] = v
    return cleaned


@dataclass(frozen=True)
class Scenario:
    slug: str
    title: str
    params: Dict[str, Any]


def _get_json(
    client: httpx.Client, path: str, *, params: Dict[str, Any]
) -> Tuple[str, int, Any]:
    url = f"{BASE_URL}{path}"
    resp = client.get(url, params=_prune_params(params))
    status = resp.status_code
    try:
        payload = resp.json()
    except Exception:
        payload = {"non_json_body": resp.text[:2000]}
    return str(resp.url), status, payload


def _get_nested(d: Any, path: List[str]) -> Any:
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _extract_overall_buckets(payload: Any) -> Optional[List[Dict[str, Any]]]:
    """Extract overall trend buckets.

    Observed shape:
      aggregations.dateRangeArea.dateRangeArea.buckets[*]
        - key_as_string
        - doc_count
    """

    buckets = _get_nested(
        payload, ["aggregations", "dateRangeArea", "dateRangeArea", "buckets"]
    )
    if isinstance(buckets, list) and (not buckets or isinstance(buckets[0], dict)):
        return buckets
    return None


def _extract_group_series(payload: Any, group: str) -> List[Dict[str, Any]]:
    """Extract grouped trend series.

    Observed shape (example group='product'):
      aggregations.product.product.buckets[*]
        - key: group value
        - trend_period.buckets[*] (time buckets)
    Returns:
      [{"group": <key>, "buckets": <trend_period buckets>, "doc_count": <total>}, ...]
    """

    group_buckets = _get_nested(payload, ["aggregations", group, group, "buckets"])
    if not isinstance(group_buckets, list):
        return []

    out: List[Dict[str, Any]] = []
    for b in group_buckets:
        if not isinstance(b, dict):
            continue
        group_key = b.get("key")
        trend_buckets = _get_nested(b, ["trend_period", "buckets"])
        if not isinstance(trend_buckets, list):
            continue
        out.append(
            {
                "group": group_key,
                "doc_count": b.get("doc_count"),
                "buckets": trend_buckets,
            }
        )
    return out


def _extract_points(series: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    """Extract (bucket_label, count) points with best-effort key guessing."""

    points_with_key: List[Tuple[Optional[int], str, float]] = []
    for row in series:
        if not isinstance(row, dict):
            continue

        # pick a time-like label
        label = (
            row.get("key_as_string")
            or row.get("date")
            or row.get("period")
            or row.get("x")
            or row.get("key")
        )
        if label is None:
            label = str(row)[:40]
        else:
            label = str(label)

        key_num: Optional[int] = None
        try:
            raw_key = row.get("key")
            if isinstance(raw_key, (int, float)):
                key_num = int(raw_key)
        except Exception:
            key_num = None

        # pick a count-like value
        count = (
            row.get("doc_count") or row.get("count") or row.get("value") or row.get("y")
        )
        if count is None:
            continue
        try:
            count_f = float(count)
        except Exception:
            continue

        points_with_key.append((key_num, label, count_f))

    # Buckets are often returned newest-first; sort chronologically when possible.
    if any(k is not None for k, _, _ in points_with_key):
        points_with_key.sort(
            key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0)
        )
    else:
        points_with_key.sort(key=lambda t: t[1])

    return [(label, count) for _, label, count in points_with_key]


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)


def compute_simple_signals(
    points: List[Tuple[str, float]],
    *,
    baseline_window: int = 8,
    min_baseline_mean: float = 10.0,
) -> Dict[str, Any]:
    """Compute simple, explainable signals from a univariate time series.

    Signals:
    - last_vs_prev: last bucket vs previous bucket (abs + pct)
    - last_vs_baseline: last bucket vs trailing baseline window (mean + z-score)

    Guardrails:
    - only compute baseline-based signals when the baseline mean is >= min_baseline_mean
      (prevents tiny denominators from looking like 'explosions')
    """

    if len(points) < 2:
        return {"error": "not_enough_points", "num_points": len(points)}

    labels = [p[0] for p in points]
    values = [p[1] for p in points]

    last_label, last_val = labels[-1], values[-1]
    prev_label, prev_val = labels[-2], values[-2]

    last_vs_prev_abs = last_val - prev_val
    last_vs_prev_pct = None
    if prev_val > 0:
        last_vs_prev_pct = (last_val / prev_val) - 1.0

    baseline_values = values[-(baseline_window + 1) : -1] if len(values) > 2 else []
    baseline_mean = _mean(baseline_values) if baseline_values else None
    baseline_sd = _stddev(baseline_values) if baseline_values else None

    z = None
    ratio = None
    if (
        baseline_mean is not None
        and baseline_mean >= min_baseline_mean
        and baseline_sd is not None
    ):
        ratio = (last_val / baseline_mean) if baseline_mean > 0 else None
        z = (last_val - baseline_mean) / baseline_sd if baseline_sd > 0 else None

    return {
        "num_points": len(points),
        "last_bucket": {"label": last_label, "count": last_val},
        "prev_bucket": {"label": prev_label, "count": prev_val},
        "signals": {
            "last_vs_prev": {
                "abs": last_vs_prev_abs,
                "pct": last_vs_prev_pct,
            },
            "last_vs_baseline": {
                "baseline_window": baseline_window,
                "baseline_mean": baseline_mean,
                "baseline_sd": baseline_sd,
                "ratio": ratio,
                "z": z,
                "min_baseline_mean": min_baseline_mean,
            },
        },
    }


def run(out_root: Path) -> Path:
    run_dir = out_root / f"signals_{_utc_stamp()}"
    _ensure_dir(run_dir)

    # A few scenarios that feel like the vision author's questions.
    # Note: we keep these broad and auditable; the goal is to understand shapes + feasibility.
    # Keep date window bounded so responses are smaller and signals are "recent".
    # This is not epoch mapping; it's just a default analysis window.
    # Default window: last ~24 months, excluding the current partial month.
    # Upstream semantics: date_received_max is exclusive (< max).
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_prefix = f"{now.year:04d}-{now.month:02d}-"
    default_date_filters = {
        "date_received_min": f"{now.year - 2:04d}-{now.month:02d}-01",
        "date_received_max": month_start.strftime("%Y-%m-%d"),
    }

    scenarios: List[Scenario] = [
        Scenario(
            slug="overall_monthly_24",
            title="Overall complaint volume (monthly, last 24 buckets)",
            params={
                "lens": "overview",
                "trend_interval": "month",
                "trend_depth": 24,
                **default_date_filters,
            },
        ),
        # Some intervals (e.g., week) may be unsupported by the upstream.
        Scenario(
            slug="overall_daily_60",
            title="Overall complaint volume (daily, last 60 buckets)",
            params={
                "lens": "overview",
                "trend_interval": "day",
                "trend_depth": 60,
                **default_date_filters,
            },
        ),
        Scenario(
            slug="product_monthly_top10",
            title="Top products over time (monthly, sub_lens product)",
            params={
                "lens": "overview",
                "trend_interval": "month",
                "trend_depth": 12,
                "sub_lens": "product",
                "sub_lens_depth": 10,
                **default_date_filters,
            },
        ),
        Scenario(
            slug="issue_monthly_top10",
            title="Top issues over time (monthly, sub_lens issue)",
            params={
                "lens": "overview",
                "trend_interval": "month",
                "trend_depth": 12,
                "sub_lens": "issue",
                "sub_lens_depth": 10,
                **default_date_filters,
            },
        ),
        Scenario(
            slug="company_monthly_top10",
            title="Top companies over time (monthly, sub_lens company)",
            params={
                "lens": "overview",
                "trend_interval": "month",
                "trend_depth": 12,
                "sub_lens": "company",
                "sub_lens_depth": 10,
                **default_date_filters,
            },
        ),
    ]

    timeout = httpx.Timeout(30.0)
    headers = {"User-Agent": "cfpb-mcp-temp-signal-explore/0.1"}

    manifest: Dict[str, Any] = {
        "base_url": BASE_URL,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scenarios": [],
    }

    with httpx.Client(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        for idx, s in enumerate(scenarios, start=1):
            url, status, payload = _get_json(client, "trends", params=s.params)

            raw_file = run_dir / f"{idx:02d}_{s.slug}.raw.json"
            _write_json(
                raw_file,
                {
                    "title": s.title,
                    "url": url,
                    "status_code": status,
                    "params": s.params,
                    "payload": payload,
                },
            )

            signals: Dict[str, Any] = {}

            overall_buckets = _extract_overall_buckets(payload)
            if overall_buckets is not None:
                overall_points = [
                    p
                    for p in _extract_points(overall_buckets)
                    if not str(p[0]).startswith(current_month_prefix)
                ]
                signals["overall"] = compute_simple_signals(overall_points)
            else:
                signals["overall"] = {
                    "error": "could_not_extract_overall_buckets",
                    "payload_top_keys": list(payload.keys())
                    if isinstance(payload, dict)
                    else None,
                }

            # If this scenario asks for a sub_lens, also compute per-group signals.
            sub_lens = s.params.get("sub_lens")
            if isinstance(sub_lens, str):
                grouped = _extract_group_series(payload, sub_lens)
                group_rows: List[Dict[str, Any]] = []
                for g in grouped:
                    buckets = g.get("buckets")
                    if not isinstance(buckets, list):
                        continue
                    points = [
                        p
                        for p in _extract_points(
                            [b for b in buckets if isinstance(b, dict)]
                        )
                        if not str(p[0]).startswith(current_month_prefix)
                    ]
                    computed = compute_simple_signals(points)
                    group_rows.append(
                        {
                            "group": g.get("group"),
                            "doc_count": g.get("doc_count"),
                            "signals": computed.get("signals"),
                            "last_bucket": computed.get("last_bucket"),
                            "prev_bucket": computed.get("prev_bucket"),
                            "num_points": computed.get("num_points"),
                        }
                    )

                # Rank by baseline z-score (when present) and by last_vs_prev percent change.
                def z_score(row: Dict[str, Any]) -> float:
                    try:
                        z = row["signals"]["last_vs_baseline"]["z"]
                        return float(z) if z is not None else float("-inf")
                    except Exception:
                        return float("-inf")

                def pct_change(row: Dict[str, Any]) -> float:
                    try:
                        pct = row["signals"]["last_vs_prev"]["pct"]
                        return float(pct) if pct is not None else float("-inf")
                    except Exception:
                        return float("-inf")

                signals["grouped"] = {
                    "group": sub_lens,
                    "num_groups": len(group_rows),
                    "top_by_z": sorted(group_rows, key=z_score, reverse=True)[:10],
                    "top_by_pct": sorted(group_rows, key=pct_change, reverse=True)[:10],
                }

            computed_file = run_dir / f"{idx:02d}_{s.slug}.computed.json"
            _write_json(
                computed_file,
                {
                    "title": s.title,
                    "url": url,
                    "status_code": status,
                    "params": s.params,
                    "signals": signals,
                },
            )

            manifest["scenarios"].append(
                {
                    "slug": s.slug,
                    "title": s.title,
                    "status_code": status,
                    "url": url,
                    "raw_file": raw_file.name,
                    "computed_file": computed_file.name,
                }
            )

    _write_json(run_dir / "manifest.json", manifest)

    md_lines: List[str] = [
        "# Signal helper exploration (proxy-based)",
        "",
        "This folder contains raw upstream trends payloads plus computed, explainable spike/velocity signals.",
        "",
        "## What this demonstrates",
        "- We can compute lightweight 'regulator signals' without local ingestion.",
        "- The value-add is ranking/flags on top of CFPB trends buckets (not changing the data).",
        "",
        "## Files",
        "- manifest.json: index of all scenarios",
        "- *.raw.json: upstream responses",
        "- *.computed.json: extracted time series + simple signals",
        "",
    ]
    _write_text(run_dir / "SUMMARY.md", "\n".join(md_lines))

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

    run_dir = run(out_root)
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
