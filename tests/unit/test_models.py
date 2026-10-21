"""models.load_cases / ShoppingCase validation."""

from decimal import Decimal
import json
from pathlib import Path

import pytest

from shop.models import AddedItem, AddStatus, CartEntry, CartSnapshot, RunResult, ShoppingCase, load_cases

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
VALID = {"name": "computers", "query": "computer", "max_price": "1500.00", "limit": 5, "seed": 17}


def write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return path


def case(**overrides: object) -> dict:
    return {**VALID, **overrides}


def test_loads_valid_cases(tmp_path: Path) -> None:
    cases = load_cases(write(tmp_path, [case(), case(name="phones", query="phone", max_price=19.99, limit=0)]))
    assert cases[0] == ShoppingCase("computers", "computer", Decimal("1500.00"), 5, 17)
    assert cases[1].max_price == Decimal("19.99")  # float in JSON -> exact decimal, not 19.989999...
    assert cases[1].limit == 0  # limit 0 is a valid (empty) search


def test_project_data_file_is_valid() -> None:
    cases = load_cases(ROOT / "data/shopping_cases.json")
    assert cases and all(isinstance(item.max_price, Decimal) for item in cases)


@pytest.mark.parametrize("price", ["abc", "", "12,50", "NaN", "Infinity", "-1", -0.01, None, True])
def test_bad_price_rejected(tmp_path: Path, price: object) -> None:
    with pytest.raises(ValueError):
        load_cases(write(tmp_path, [case(max_price=price)]))


@pytest.mark.parametrize("limit", [-1, "5", 2.0, True, None])
def test_bad_limit_rejected(tmp_path: Path, limit: object) -> None:
    with pytest.raises(ValueError, match="limit"):
        load_cases(write(tmp_path, [case(limit=limit)]))


@pytest.mark.parametrize("seed", ["1", 1.5, None, False])
def test_non_int_seed_rejected(tmp_path: Path, seed: object) -> None:
    with pytest.raises(ValueError, match="seed"):
        load_cases(write(tmp_path, [case(seed=seed)]))


@pytest.mark.parametrize("field", ["name", "query"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_name_or_query_rejected(tmp_path: Path, field: str, value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        load_cases(write(tmp_path, [case(**{field: value})]))


def test_duplicate_names_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unique"):
        load_cases(write(tmp_path, [case(), case(query="other")]))


@pytest.mark.parametrize("content", ["", "[]", "{}", '"text"', "null"])
def test_empty_or_non_list_file_rejected(tmp_path: Path, content: str) -> None:
    with pytest.raises(ValueError):  # json.JSONDecodeError is a ValueError too
        load_cases(write(tmp_path, content))


@pytest.mark.parametrize("missing", ["name", "query", "max_price", "limit", "seed"])
def test_missing_key_rejected(tmp_path: Path, missing: str) -> None:
    row = case()
    del row[missing]
    with pytest.raises(ValueError, match=missing):
        load_cases(write(tmp_path, [row]))


@pytest.mark.parametrize(
    "rows",
    [[case(name=123)], [case(query=["computer"])], ["computer"]],
    ids=["name-int", "query-list", "row-not-object"],
)
def test_wrong_json_types_raise_value_error(tmp_path: Path, rows: list) -> None:
    with pytest.raises(ValueError):
        load_cases(write(tmp_path, rows))


def test_cart_snapshot_quantity_and_run_result_filter() -> None:
    entries = [CartEntry("A", 2, Decimal("1"), Decimal("2")), CartEntry("B", 1, Decimal("3"), Decimal("3"))]
    snapshot = CartSnapshot(entries, Decimal("5"))
    assert snapshot.quantity == 3
    items = [AddedItem("u1", "A", AddStatus.ADDED), AddedItem("u2", "B", AddStatus.UNAVAILABLE)]
    result = RunResult(["u1", "u2"], items, snapshot)
    assert [item.url for item in result.with_status(AddStatus.ADDED)] == ["u1"]
    assert result.with_status(AddStatus.REJECTED) == []


# ------------------------------------------------------------- optional fields (search options, expectations)


def test_optional_fields_default() -> None:
    loaded = ShoppingCase("a", "abc", Decimal("1"), 5, 1)
    assert (loaded.search_in_descriptions, loaded.expect_empty, loaded.min_results, loaded.min_search_pages) == (
        False,
        False,
        0,
        1,
    )


def test_optional_fields_loaded(tmp_path: Path) -> None:
    row = case(search_in_descriptions=True, min_results=5, min_search_pages=2)
    loaded = load_cases(write(tmp_path, [row, case(name="empty", expect_empty=True)]))
    assert loaded[0].search_in_descriptions is True
    assert (loaded[0].min_results, loaded[0].min_search_pages) == (5, 2)
    assert loaded[1].expect_empty is True


@pytest.mark.parametrize("field", ["search_in_descriptions", "expect_empty"])
@pytest.mark.parametrize("value", ["true", 1, 0, None, "yes"])
def test_flags_must_be_booleans(tmp_path: Path, field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        load_cases(write(tmp_path, [case(**{field: value})]))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"min_results": -1}, ">= 0"),
        ({"min_results": "3"}, "min_results must be an integer"),
        ({"min_results": 2.0}, "min_results must be an integer"),
        ({"min_results": True}, "min_results must be an integer"),
        ({"min_search_pages": 0}, "min_search_pages >= 1"),
        ({"min_search_pages": -2}, "min_search_pages >= 1"),
        ({"min_search_pages": "2"}, "min_search_pages must be an integer"),
        ({"min_results": 6, "limit": 5}, "cannot exceed limit"),
    ],
)
def test_bad_expectations_rejected(tmp_path: Path, overrides: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_cases(write(tmp_path, [case(**overrides)]))


def test_min_results_equal_to_limit_is_fine(tmp_path: Path) -> None:
    assert load_cases(write(tmp_path, [case(min_results=5, limit=5)]))[0].min_results == 5


@pytest.mark.parametrize(
    "overrides",
    [
        {"expect_empty": True, "min_results": 1},
        {"expect_empty": True, "min_search_pages": 2},
    ],
)
def test_expect_empty_contradictions_rejected(tmp_path: Path, overrides: dict) -> None:
    with pytest.raises(ValueError, match="contradicts"):
        load_cases(write(tmp_path, [case(**overrides)]))


def test_expect_empty_with_default_expectations_is_fine(tmp_path: Path) -> None:
    loaded = load_cases(write(tmp_path, [case(expect_empty=True, min_results=0, min_search_pages=1)]))
    assert loaded[0].expect_empty


def test_limit_zero_with_min_search_pages_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_cases(write(tmp_path, [case(limit=0, min_search_pages=3)]))


@pytest.mark.parametrize("extra", [{"maxprice": "10"}, {"Name": "x"}, {"min_result": 1, "pages": 2}])
def test_unknown_keys_rejected(tmp_path: Path, extra: dict) -> None:
    with pytest.raises(ValueError, match="unknown key") as error:
        load_cases(write(tmp_path, [case(**extra)]))
    for key in extra:
        assert repr(key) in str(error.value)


@pytest.mark.parametrize("price", [True, False, [1500], {"amount": 1}, None])
def test_max_price_must_be_number_or_string(tmp_path: Path, price: object) -> None:
    with pytest.raises(ValueError, match="max_price"):
        load_cases(write(tmp_path, [case(max_price=price)]))


def test_max_price_nan_literal_rejected(tmp_path: Path) -> None:
    row = json.dumps(case()).replace('"1500.00"', "NaN")  # Python's json accepts the NaN literal
    with pytest.raises(ValueError, match="finite"):
        load_cases(write(tmp_path, f"[{row}]"))


@pytest.mark.parametrize(("price", "expected"), [(1500, "1500"), (19.99, "19.99"), (" 12.50 ", "12.50")])
def test_max_price_accepted_forms(tmp_path: Path, price: object, expected: str) -> None:
    assert load_cases(write(tmp_path, [case(max_price=price)]))[0].max_price == Decimal(expected)


def test_unparseable_max_price_message_names_the_field(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"max_price.*'abc'"):
        load_cases(write(tmp_path, [case(max_price="abc")]))


@pytest.mark.parametrize("value", [0, -1, 1.5, "3", True])
def test_max_quantity_must_be_a_positive_integer(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError, match="max_quantity"):
        load_cases(write(tmp_path, [case(max_quantity=value)]))


def test_max_quantity_defaults_to_one_unit(tmp_path: Path) -> None:
    assert load_cases(write(tmp_path, [case()]))[0].max_quantity == 1
    assert load_cases(write(tmp_path, [case(max_quantity=3)]))[0].max_quantity == 3
