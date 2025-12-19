"""Smoke tests for Phase 4.5: CFPB UI integration (URL generation and screenshots)."""

import pytest


def test_cfpb_ui_url_generation_smoke(client):
    """Test that the URL generator returns a well-formed CFPB dashboard link."""
    r = client.get(
        "/cfpb-ui/url",
        params={
            "search_term": "foreclosure",
            "date_received_min": "2020-01-01",
            "date_received_max": "2023-12-31",
            "product": ["Mortgage"],
        },
    )
    r.raise_for_status()
    data = r.json()

    assert "url" in data
    url = data["url"]
    assert isinstance(url, str)
    assert url.startswith(
        "https://www.consumerfinance.gov/data-research/consumer-complaints/search/"
    )
    assert "searchText=foreclosure" in url
    assert "date_received_min=2020-01-01" in url
    assert "product=Mortgage" in url


def test_cfpb_ui_url_with_multiple_filters(client):
    """Test URL generation with multiple filter values."""
    r = client.get(
        "/cfpb-ui/url",
        params={
            "company": ["Bank of America", "Wells Fargo"],
            "state": ["CA", "NY"],
        },
    )
    r.raise_for_status()
    data = r.json()

    url = data["url"]
    # Should comma-separate multiple values
    assert "company=" in url
    assert "state=" in url


def test_cfpb_ui_url_empty_filters(client):
    """Test that empty filters return just the base URL."""
    r = client.get("/cfpb-ui/url")
    r.raise_for_status()
    data = r.json()

    # Should return base URL without query params
    assert (
        data["url"]
        == "https://www.consumerfinance.gov/data-research/consumer-complaints/search/"
    )


@pytest.mark.integration
def test_cfpb_ui_screenshot_availability(client):
    """Test that the screenshot endpoint is reachable (may return 503 if Playwright not initialized)."""
    r = client.get(
        "/cfpb-ui/screenshot",
        params={"search_term": "test"},
    )

    # Either 200 (screenshot succeeded) or 503 (Playwright unavailable in test env)
    assert r.status_code in {200, 503}

    if r.status_code == 200:
        # Should return PNG image
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 1000  # Reasonable minimum for a PNG
    else:
        # Should return JSON error
        data = r.json()
        assert "detail" in data
        assert "Playwright" in data["detail"] or "unavailable" in data["detail"].lower()
