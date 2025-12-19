import pytest


def _default_date_window() -> tuple[str, str, str]:
    """Return (date_received_min, date_received_max, current_month_prefix).

    We pin max to the first day of the current month to avoid partial-month artifacts.
    """

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    date_received_max = month_start.strftime("%Y-%m-%d")
    date_received_min = f"{now.year - 2:04d}-{now.month:02d}-01"
    current_month_prefix = f"{now.year:04d}-{now.month:02d}-"
    return date_received_min, date_received_max, current_month_prefix


def test_search_smoke(client):
    r = client.get("/search", params={"size": 1})
    r.raise_for_status()
    data = r.json()
    assert "hits" in data


def test_trends_smoke(client):
    r = client.get("/trends", params={"trend_depth": 5})
    r.raise_for_status()
    data = r.json()
    # trends responses are aggregation-centric; just assert it's JSON
    assert isinstance(data, dict)


def test_geo_states_smoke(client):
    r = client.get("/geo/states")
    r.raise_for_status()
    data = r.json()
    assert isinstance(data, dict)


@pytest.mark.parametrize("field", ["company", "zip_code"])
def test_suggest_smoke(client, field):
    r = client.get(
        f"/suggest/{field}",
        params={"text": "bank" if field == "company" else "90", "size": 3},
    )
    r.raise_for_status()
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 3


def test_suggest_invalid_field_422(client):
    r = client.get("/suggest/badfield", params={"text": "x"})
    assert r.status_code == 422


def test_document_round_trip_from_search(client):
    search = client.get("/search", params={"size": 1})
    search.raise_for_status()
    hits = search.json().get("hits", {}).get("hits", [])
    assert hits, "Expected at least one search hit"

    # CFPB returns ES-style docs; id may be in _id or in _source.
    hit = hits[0]
    complaint_id = hit.get("_id") or hit.get("_source", {}).get("complaint_id")
    assert complaint_id, f"Could not find complaint id in hit: {hit.keys()}"

    doc = client.get(f"/complaint/{complaint_id}")
    doc.raise_for_status()
    assert isinstance(doc.json(), dict)


def test_signals_overall_smoke(client):
    date_min, date_max, current_month_prefix = _default_date_window()
    r = client.get(
        "/signals/overall",
        params={"date_received_min": date_min, "date_received_max": date_max},
    )
    r.raise_for_status()
    data = r.json()
    assert isinstance(data, dict)
    overall = (data.get("signals") or {}).get("overall")
    assert isinstance(overall, dict)
    last_bucket = overall.get("last_bucket")
    assert isinstance(last_bucket, dict)
    # Guardrail: we should not be scoring on the current-month partial bucket.
    assert not str(last_bucket.get("label", "")).startswith(current_month_prefix)


@pytest.mark.parametrize("group", ["product", "issue"])
def test_signals_group_smoke(client, group):
    date_min, date_max, _ = _default_date_window()
    r = client.get(
        "/signals/group",
        params={
            "group": group,
            "date_received_min": date_min,
            "date_received_max": date_max,
            "top_n": 5,
        },
    )
    r.raise_for_status()
    data = r.json()
    assert isinstance(data, dict)
    results = data.get("results")
    assert isinstance(results, list)
    assert len(results) <= 5
    if results:
        row0 = results[0]
        assert isinstance(row0, dict)
        assert "group" in row0
        assert "signals" in row0


def test_signals_company_smoke(client):
    date_min, date_max, _ = _default_date_window()
    r = client.get(
        "/signals/company",
        params={
            "date_received_min": date_min,
            "date_received_max": date_max,
            "top_n": 5,
        },
    )
    r.raise_for_status()
    data = r.json()
    assert isinstance(data, dict)
    results = data.get("results")
    assert isinstance(results, list)
    assert len(results) <= 5
    if results:
        row0 = results[0]
        assert isinstance(row0, dict)
        assert "company" in row0
        assert "computed" in row0
