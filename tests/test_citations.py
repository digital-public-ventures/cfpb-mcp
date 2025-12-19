"""Tests for Phase 4.6 citation URL generation."""

import pytest
from server import build_cfpb_ui_url, generate_citations


class TestBuildCfpbUiUrl:
    """Test URL construction for CFPB UI deep-links."""

    def test_basic_search_url(self):
        """Test simple search query URL."""
        url = build_cfpb_ui_url(
            search_term="foreclosure", product=["Mortgage"], tab="List"
        )
        assert "searchText=foreclosure" in url
        assert "product=Mortgage" in url
        assert "tab=List" in url
        assert url.startswith(
            "https://www.consumerfinance.gov/data-research/consumer-complaints/search/?"
        )

    def test_trends_url(self):
        """Test trends view URL with lens and chart type."""
        url = build_cfpb_ui_url(
            product=["Mortgage"],
            date_received_min="2020-01-01",
            date_received_max="2023-12-31",
            tab="Trends",
            lens="Product",
            chart_type="line",
            date_interval="Month",
        )
        assert "tab=Trends" in url
        assert "lens=Product" in url
        assert "chartType=line" in url
        assert "dateInterval=Month" in url
        assert "product=Mortgage" in url
        assert "date_received_min=2020-01-01" in url

    def test_map_url(self):
        """Test geographic map view URL."""
        url = build_cfpb_ui_url(
            product=["Mortgage"], state=["CA", "TX", "FL"], tab="Map"
        )
        assert "tab=Map" in url
        assert "product=Mortgage" in url
        assert "state=CA%2CTX%2CFL" in url

    def test_multi_value_params(self):
        """Test multiple products/issues/states."""
        url = build_cfpb_ui_url(
            product=["Mortgage", "Debt collection"],
            issue=["Trouble during payment process"],
            state=["TX", "FL"],
        )
        assert "product=Mortgage%2CDebt+collection" in url
        assert "issue=Trouble+during+payment+process" in url
        assert "state=TX%2CFL" in url

    def test_boolean_params(self):
        """Test boolean parameters like has_narrative."""
        url = build_cfpb_ui_url(has_narrative="true", tab="List")
        assert "has_narrative=true" in url

    def test_no_params_returns_base_url(self):
        """Test that no parameters returns just the base URL."""
        url = build_cfpb_ui_url()
        assert (
            url
            == "https://www.consumerfinance.gov/data-research/consumer-complaints/search/"
        )

    def test_company_response_params(self):
        """Test company response filtering."""
        url = build_cfpb_ui_url(
            company_response=["Closed with explanation", "Closed with monetary relief"],
            tab="List",
        )
        assert (
            "company_response=Closed+with+explanation%2CClosed+with+monetary+relief"
            in url
        )

    def test_special_characters_encoded(self):
        """Test URL encoding of special characters."""
        url = build_cfpb_ui_url(
            search_term="mortgage scam", company=["WELLS FARGO & COMPANY"]
        )
        assert "searchText=mortgage+scam" in url
        assert "company=WELLS+FARGO+%26+COMPANY" in url


class TestGenerateCitations:
    """Test citation generation for different query contexts."""

    def test_search_citations(self):
        """Test citations for search queries."""
        citations = generate_citations(
            context_type="search",
            total_hits=1234,
            search_term="foreclosure",
            product=["Mortgage"],
            date_received_min="2023-01-01",
            date_received_max="2023-12-31",
        )

        assert len(citations) == 1
        assert citations[0]["type"] == "search_results"
        assert "tab=List" in citations[0]["url"]
        assert "searchText=foreclosure" in citations[0]["url"]
        assert "product=Mortgage" in citations[0]["url"]
        assert "1,234" in citations[0]["description"]

    def test_trends_citations(self):
        """Test citations for trend queries."""
        citations = generate_citations(
            context_type="trends",
            lens="Product",
            product=["Mortgage"],
            date_received_min="2022-01-01",
        )

        assert len(citations) == 2
        # First citation should be trends chart
        assert citations[0]["type"] == "trends_chart"
        assert "tab=Trends" in citations[0]["url"]
        assert "lens=Product" in citations[0]["url"]
        assert "chartType=line" in citations[0]["url"]
        assert "dateInterval=Month" in citations[0]["url"]
        # Second citation should be list view
        assert citations[1]["type"] == "search_results"
        assert "tab=List" in citations[1]["url"]

    def test_geo_citations(self):
        """Test citations for geographic queries."""
        citations = generate_citations(
            context_type="geo",
            product=["Mortgage"],
            state=["CA"],
        )

        assert len(citations) == 2
        # First citation should be map view
        assert citations[0]["type"] == "geographic_map"
        assert "tab=Map" in citations[0]["url"]
        # Second citation should be list view
        assert citations[1]["type"] == "search_results"
        assert "tab=List" in citations[1]["url"]

    def test_document_citations(self):
        """Test citations for individual complaint documents."""
        citations = generate_citations(
            context_type="document",
            complaint_id="12345678",
        )

        assert len(citations) == 1
        assert citations[0]["type"] == "complaint_detail"
        assert "12345678" in citations[0]["description"]

    def test_citations_with_multiple_filters(self):
        """Test citations with complex filter combinations."""
        citations = generate_citations(
            context_type="search",
            total_hits=500,
            search_term="scam",
            product=["Debt collection", "Credit reporting"],
            state=["TX", "FL", "CA"],
            date_received_min="2020-01-01",
            has_narrative="true",
            company_response=["Closed with explanation"],
        )

        url = citations[0]["url"]
        assert "searchText=scam" in url
        assert "product=Debt+collection%2CCredit+reporting" in url
        assert "state=TX%2CFL%2CCA" in url
        assert "date_received_min=2020-01-01" in url
        assert "has_narrative=true" in url
        assert "company_response=Closed+with+explanation" in url

    def test_citations_without_filters(self):
        """Test citations with minimal filters."""
        citations = generate_citations(
            context_type="search",
            total_hits=100,
        )

        assert len(citations) == 1
        # Should still generate valid base URL
        assert citations[0]["url"].startswith(
            "https://www.consumerfinance.gov/data-research/consumer-complaints/search/"
        )

    def test_trends_with_lens(self):
        """Test trends citations respect lens parameter."""
        citations = generate_citations(
            context_type="trends",
            lens="Company",
            company=["BANK OF AMERICA"],
        )

        assert "lens=Company" in citations[0]["url"]
        assert citations[0]["type"] == "trends_chart"

    def test_citation_descriptions(self):
        """Test that citation descriptions are meaningful."""
        # Search with count
        search_cites = generate_citations(
            context_type="search", total_hits=42, product=["Mortgage"]
        )
        assert "42" in search_cites[0]["description"]
        assert "CFPB.gov" in search_cites[0]["description"]

        # Trends
        trend_cites = generate_citations(context_type="trends", lens="Overview")
        assert "Interactive" in trend_cites[0]["description"]
        assert "trends" in trend_cites[0]["description"].lower()

        # Geo
        geo_cites = generate_citations(context_type="geo")
        assert "map" in geo_cites[0]["description"].lower()
