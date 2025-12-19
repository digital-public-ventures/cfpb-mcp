import pytest

from server import build_params, prune_params


def test_prune_params_drops_none_and_empty_strings() -> None:
    assert prune_params({"a": None, "b": "", "c": "  ", "d": "ok"}) == {"d": "ok"}


def test_prune_params_drops_empty_lists_and_empty_list_items() -> None:
    assert prune_params(
        {"a": [], "b": [""], "c": [" ", None], "d": ["x", "", "y"]}
    ) == {"d": ["x", "y"]}


def test_prune_params_keeps_non_string_values() -> None:
    assert prune_params({"a": 0, "b": False, "c": True, "d": 3.14}) == {
        "a": 0,
        "b": False,
        "c": True,
        "d": 3.14,
    }


def test_build_params_filters_empty_values() -> None:
    params = build_params(
        search_term="",
        field=None,
        company=["", "Acme Bank"],
        issue=["   ", "Fees"],
        state=[],
        tags=None,
    )

    # build_params returns already-pruned params
    assert "search_term" not in params
    assert "field" not in params
    assert params["company"] == ["Acme Bank"]
    assert params["issue"] == ["Fees"]
    assert "state" not in params
    assert "tags" not in params


@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"x": "y"}, {"x": "y"}),
        ({"x": ["y"]}, {"x": ["y"]}),
        ({"x": [1, 2, 3]}, {"x": [1, 2, 3]}),
    ],
)
def test_prune_params_smoke(raw, expected) -> None:
    assert prune_params(raw) == expected
