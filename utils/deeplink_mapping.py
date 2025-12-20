from __future__ import annotations

import re
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional
from urllib.parse import parse_qs, urlencode, urlparse

UI_BASE_URL = (
    "https://www.consumerfinance.gov/data-research/consumer-complaints/search/"
)
DEFAULT_START_DATE = "2011-12-01"

API_TO_URL_PARAM = {
    "search_term": "searchText",
    "field": "searchField",
    "sub_lens": "subLens",
    "trend_interval": "dateInterval",
}

URL_TO_API_PARAM = {
    "searchText": "search_term",
    "searchField": "field",
    "subLens": "sub_lens",
    "dateInterval": "trend_interval",
    "page": "frm",
}

SEARCH_ENDPOINT_KEYS = {
    "search_term",
    "field",
    "frm",
    "size",
    "sort",
    "format",
    "no_aggs",
    "no_highlight",
    "company",
    "company_public_response",
    "company_received_max",
    "company_received_min",
    "company_response",
    "consumer_consent_provided",
    "consumer_disputed",
    "date_received_max",
    "date_received_min",
    "has_narrative",
    "issue",
    "product",
    "search_after",
    "state",
    "submitted_via",
    "tags",
    "timely",
    "zip_code",
}

GEO_ENDPOINT_KEYS = {
    "search_term",
    "field",
    "company",
    "company_public_response",
    "company_received_max",
    "company_received_min",
    "company_response",
    "consumer_consent_provided",
    "consumer_disputed",
    "date_received_max",
    "date_received_min",
    "has_narrative",
    "issue",
    "product",
    "state",
    "submitted_via",
    "tags",
    "timely",
    "zip_code",
}

TRENDS_ENDPOINT_KEYS = {
    "search_term",
    "field",
    "company",
    "company_public_response",
    "company_received_max",
    "company_received_min",
    "company_response",
    "consumer_consent_provided",
    "consumer_disputed",
    "date_received_max",
    "date_received_min",
    "focus",
    "has_narrative",
    "issue",
    "lens",
    "product",
    "state",
    "submitted_via",
    "sub_lens",
    "sub_lens_depth",
    "tags",
    "timely",
    "trend_depth",
    "trend_interval",
    "zip_code",
}

TREND_KEYS = {
    "lens",
    "sub_lens",
    "trend_interval",
    "trend_depth",
    "sub_lens_depth",
    "focus",
    "chartType",
}


@dataclass(frozen=True)
class ValidationResult:
    unknown_keys: tuple[str, ...]
    allowed_keys: tuple[str, ...]


def _clean_value(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in {"true", "false"}:
            return lowered
        return cleaned
    if isinstance(value, list):
        cleaned_items = []
        for item in value:
            cleaned_item = _clean_value(item)
            if cleaned_item is None:
                continue
            cleaned_items.append(cleaned_item)
        if not cleaned_items:
            return None
        return cleaned_items
    return value


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _format_trend_interval(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return value
    tokens = re.split(r"[\s_-]+", cleaned)
    return " ".join(token.capitalize() for token in tokens if token)


def _format_lens(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return value
    return re.sub(r"[\s-]+", "_", cleaned).lower()


def normalize_api_params(api_params: Mapping[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, raw_value in api_params.items():
        cleaned_value = _clean_value(raw_value)
        if cleaned_value is None:
            continue
        if key == "trend_interval" and isinstance(cleaned_value, str):
            cleaned_value = cleaned_value.lower()
        if key in {"lens", "sub_lens"} and isinstance(cleaned_value, str):
            cleaned_value = _format_lens(cleaned_value)
        normalized[key] = cleaned_value
    return normalized


def _default_end_date(today: Optional[date] = None) -> str:
    """Return the last day of the month before (today - 30 days)."""
    anchor = today or date.today()
    cutoff = anchor - timedelta(days=30)
    first_of_cutoff_month = cutoff.replace(day=1)
    end_date = first_of_cutoff_month - timedelta(days=1)
    return end_date.strftime("%Y-%m-%d")


def apply_default_dates(
    api_params: Mapping[str, Any], today: Optional[date] = None
) -> Dict[str, Any]:
    """Return a copy of params with explicit date_received_min/max defaults."""
    params_with_dates = dict(api_params)
    # The CFPB UI defaults to a recent date range (last three years) when omitted.
    # We explicitly set dates for stability and API/UI parity.
    if (
        "date_received_min" not in params_with_dates
        or params_with_dates.get("date_received_min") is None
    ):
        params_with_dates["date_received_min"] = DEFAULT_START_DATE
    if (
        "date_received_max" not in params_with_dates
        or params_with_dates.get("date_received_max") is None
    ):
        params_with_dates["date_received_max"] = _default_end_date(today=today)
    return params_with_dates


def validate_api_params(
    api_params: Mapping[str, Any], allowed_keys: Iterable[str]
) -> ValidationResult:
    allowed = set(allowed_keys)
    unknown = tuple(sorted(key for key in api_params if key not in allowed))
    return ValidationResult(unknown_keys=unknown, allowed_keys=tuple(sorted(allowed)))


def api_params_to_url_params(api_params: Mapping[str, Any]) -> Dict[str, Any]:
    url_params: Dict[str, Any] = {}
    normalized = normalize_api_params(api_params)

    for key, value in normalized.items():
        if key == "frm":
            continue
        mapped_key = API_TO_URL_PARAM.get(key, key)
        mapped_value = value
        if key == "trend_interval" and isinstance(mapped_value, str):
            mapped_value = _format_trend_interval(mapped_value)
        if key in {"lens", "sub_lens"} and isinstance(mapped_value, str):
            mapped_value = _format_lens(mapped_value)
        url_params[mapped_key] = mapped_value

    _apply_pagination(normalized, url_params)
    return url_params


def _apply_pagination(api_params: Mapping[str, Any], url_params: Dict[str, Any]) -> None:
    frm = _parse_int(api_params.get("frm"))
    size = _parse_int(api_params.get("size"))
    if frm is None or size in (None, 0):
        return
    url_params["page"] = (frm // size) + 1


def build_deeplink_url(
    api_params: Mapping[str, Any],
    *,
    tab: Optional[str] = None,
    today: Optional[date] = None,
) -> str:
    params_with_dates = apply_default_dates(api_params, today=today)
    url_params = api_params_to_url_params(params_with_dates)

    if tab is None and any(key in api_params for key in TREND_KEYS):
        tab = "Trends"
    if tab:
        url_params["tab"] = tab

    if not url_params:
        return UI_BASE_URL

    return f"{UI_BASE_URL}?{urlencode(url_params, doseq=True)}"


def url_params_to_api_params(url_params: Mapping[str, Any]) -> Dict[str, Any]:
    api_params: Dict[str, Any] = {}
    for key, raw_value in url_params.items():
        api_key = URL_TO_API_PARAM.get(key, key)
        cleaned_value = _clean_value(raw_value)
        if cleaned_value is None:
            continue
        if api_key == "trend_interval" and isinstance(cleaned_value, str):
            cleaned_value = cleaned_value.lower()
        if api_key in {"lens", "sub_lens"} and isinstance(cleaned_value, str):
            cleaned_value = _format_lens(cleaned_value)
        api_params[api_key] = cleaned_value

    if "frm" in api_params:
        page = _parse_int(api_params.get("frm"))
        size = _parse_int(api_params.get("size"))
        if page is not None and size:
            api_params["frm"] = (page - 1) * size
        else:
            api_params.pop("frm", None)

    return api_params


def url_to_api_params(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    flattened = {k: v if len(v) > 1 else v[0] for k, v in query.items()}
    return url_params_to_api_params(flattened)
