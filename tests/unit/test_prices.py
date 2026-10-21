"""prices.parse_price: amounts as the shop displays them."""

from decimal import Decimal

import pytest

from shop.prices import parse_price

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("800.00", "800.00"),
        ("1200", "1200"),
        ("0.00", "0.00"),
        ("1,215.00", "1215.00"),
        ("12,345,678.90", "12345678.90"),
        ("1,000", "1000"),
        ("From 500.00", "500.00"),
        ("Sub-Total: 1,215.00", "1215.00"),
        ("Price: $25.00 USD", "25.00"),
        ("\n   1590.00            \n", "1590.00"),
        ("2.5 GHz Intel Pentium Dual-Core E2200 [+15.00]", "2.5"),  # first amount wins
    ],
)
def test_parses_first_amount(text: str, expected: str) -> None:
    result = parse_price(text)
    assert isinstance(result, Decimal)
    assert result == Decimal(expected)
    assert str(result) == expected  # exact decimal digits, no float rounding


def test_thousands_separator_is_not_a_decimal_point() -> None:
    assert parse_price("1,590.00") > Decimal("1500")


@pytest.mark.parametrize("text", ["1.234,56 ₪", "12,5", "1 234,56 €", "1,23", "1,2345.00"])
def test_other_formats_raise_instead_of_a_wrong_amount(text: str) -> None:
    with pytest.raises(ValueError, match="Unsupported price format"):
        parse_price(text)


@pytest.mark.parametrize("text", ["", "   ", "Call for pricing", "Free", "-.-"])
def test_no_number_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError, match="No price found"):
        parse_price(text)
