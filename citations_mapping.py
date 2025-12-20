"""Compatibility wrapper for the deeplink mapping helpers."""

from utils.deeplink_mapping import (  # noqa: F401
    UI_BASE_URL,
    apply_default_dates,
    api_params_to_url_params,
    build_deeplink_url,
    normalize_api_params,
    url_params_to_api_params,
    url_to_api_params,
)


def map_api_params_to_url_params(api_params):
    return api_params_to_url_params(api_params)
