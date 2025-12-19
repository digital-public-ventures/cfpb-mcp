"""Pipeline-style 'signal helper' exploration: company spikes using search -> trends.

Idea:
- Upstream trends may not provide a direct company grouping.
- But upstream search aggregations *do* expose top companies.
- So a proxy-based helper can:
  1) call search with broad filters to get top companies
  2) for each company, call trends filtered to that company
  3) compute a simple spike/velocity score and rank

Usage:
  uv run python temp/company_signal_pipeline.py --out temp/output

Outputs:
- Writes files to temp/output/company_signals_<timestamp>/
- Minimal terminal output (prints run directory only)
"""

from __future__ import annotations

import argparse
import json
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


def _prune(params: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
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
            out[k] = vv
            continue
        out[k] = v
    return out


def _extract_points_date_range_area(payload: Any) -> List[Tuple[str, float]]:
    """Extract overall time series from trends payload (chronological)."""
    buckets = (
        payload.get("aggregations", {})
        .get("dateRangeArea", {})
        .get("dateRangeArea", {})
        .get("buckets")
    )
    if not isinstance(buckets, list):
        return []

    rows: List[Tuple[int, str, float]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        key = b.get("key")
        label = b.get("key_as_string")
        count = b.get("doc_count")
        if not isinstance(key, (int, float)) or label is None or count is None:
            continue
        try:
            rows.append((int(key), str(label), float(count)))
        except Exception:
            continue

    rows.sort(key=lambda t: t[0])
    return [(label, count) for _, label, count in rows]


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return var**0.5


def _signals(
    points: List[Tuple[str, float]],
    *,
    baseline_window: int = 8,
    min_baseline_mean: float = 25.0,
) -> Dict[str, Any]:
    if len(points) < 2:
        return {"error": "not_enough_points", "num_points": len(points)}

    labels = [p[0] for p in points]
    values = [p[1] for p in points]

    last_label, last_val = labels[-1], values[-1]
    prev_label, prev_val = labels[-2], values[-2]

    pct = None
    if prev_val > 0:
        pct = (last_val / prev_val) - 1.0

    baseline = values[-(baseline_window + 1) : -1]
    baseline_mean = _mean(baseline) if baseline else None
    baseline_sd = _stddev(baseline) if baseline else None

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
        "last_bucket": {"label": last_label, "count": last_val},
        "prev_bucket": {"label": prev_label, "count": prev_val},
        "signals": {
            "last_vs_prev": {"pct": pct, "abs": last_val - prev_val},
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


def _company_buckets_from_search(payload: Any) -> List[Tuple[str, int]]:
    buckets = (
        payload.get("aggregations", {})
        .get("company", {})
        .get("company", {})
        .get("buckets")
    )
    if not isinstance(buckets, list):
        return []

    out: List[Tuple[str, int]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        key = b.get("key")
        doc_count = b.get("doc_count")
        if not isinstance(key, str) or not isinstance(doc_count, int):
            continue
        out.append((key, doc_count))

    out.sort(key=lambda t: t[1], reverse=True)
    return out


def run(out_root: Path) -> Path:
    run_dir = out_root / f"company_signals_{_utc_stamp()}"
    _ensure_dir(run_dir)

    timeout = httpx.Timeout(30.0)
    headers = {"User-Agent": "cfpb-mcp-temp-company-signal/0.1"}

    # "Vision author"-flavored defaults: recent window, broad market view.
    # Exclude the current partial month to avoid false "drops".
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_prefix = f"{now.year:04d}-{now.month:02d}-"
    date_filters = {
        "date_received_min": f"{now.year - 2:04d}-{now.month:02d}-01",
        "date_received_max": month_start.strftime("%Y-%m-%d"),
    }

    # Step 1: find top companies from search aggregations.
    search_params = {
        "size": 0,
        "frm": 0,
        "no_highlight": True,
        "no_aggs": False,
        "sort": "created_date_desc",
        **date_filters,
    }

    with httpx.Client(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        search_resp = client.get(BASE_URL, params=_prune(search_params))
        search_payload = (
            search_resp.json()
            if search_resp.status_code == 200
            else {"status": search_resp.status_code, "body": search_resp.text[:2000]}
        )
        _write_json(
            run_dir / "01_search_for_top_companies.raw.json",
            {
                "url": str(search_resp.url),
                "status_code": search_resp.status_code,
                "params": search_params,
                "payload": search_payload,
            },
        )

        company_buckets = _company_buckets_from_search(
            search_payload if isinstance(search_payload, dict) else {}
        )
        top_n = 10
        top_companies = company_buckets[:top_n]
        _write_json(
            run_dir / "02_top_companies.json",
            {
                "top_n": top_n,
                "companies": [{"company": c, "doc_count": n} for c, n in top_companies],
            },
        )

        # Step 2: for each company, fetch trends filtered by company and compute signals.
        results: List[Dict[str, Any]] = []
        for idx, (company, total) in enumerate(top_companies, start=1):
            trends_params = {
                "lens": "overview",
                "trend_interval": "month",
                "trend_depth": 12,
                "company": [company],
                **date_filters,
            }
            trends_resp = client.get(f"{BASE_URL}trends", params=_prune(trends_params))
            try:
                trends_payload = trends_resp.json()
            except Exception:
                trends_payload = {"non_json_body": trends_resp.text[:2000]}

            # Save raw for transparency (limited to top 10, so manageable)
            _write_json(
                run_dir / f"03_trends_{idx:02d}.raw.json",
                {
                    "company": company,
                    "company_doc_count": total,
                    "url": str(trends_resp.url),
                    "status_code": trends_resp.status_code,
                    "params": trends_params,
                    "payload": trends_payload,
                },
            )

            points = _extract_points_date_range_area(
                trends_payload if isinstance(trends_payload, dict) else {}
            )
            points = [
                p for p in points if not str(p[0]).startswith(current_month_prefix)
            ]
            computed = _signals(points)
            results.append(
                {
                    "company": company,
                    "company_doc_count": total,
                    "status_code": trends_resp.status_code,
                    "computed": computed,
                }
            )

        # Rank by z-score when present
        def z_score(row: Dict[str, Any]) -> float:
            try:
                z = row["computed"]["signals"]["last_vs_baseline"]["z"]
                return float(z) if z is not None else float("-inf")
            except Exception:
                return float("-inf")

        ranked = sorted(results, key=z_score, reverse=True)

        _write_json(
            run_dir / "04_ranked_company_spikes.json",
            {
                "date_filters": date_filters,
                "top_companies_basis": "search aggregations.company.company.buckets",
                "ranking": "last bucket vs baseline z-score",
                "results": ranked,
            },
        )

    (run_dir / "SUMMARY.md").write_text(
        "\n".join(
            [
                "# Company spike pipeline (proxy-based)",
                "",
                "This demonstrates a realistic Phase 4-style 'signal helper' that is actually a pipeline of upstream calls:",
                "1) search (aggregations) -> top companies",
                "2) trends per company -> time series",
                "3) simple spike scoring -> ranked results",
                "",
                "See 04_ranked_company_spikes.json for the main output.",
            ]
        ),
        encoding="utf-8",
    )

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
