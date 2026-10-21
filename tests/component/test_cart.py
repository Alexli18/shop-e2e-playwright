"""CartPage / CartTable / CartTotals and the workflow's assert_cart_total_not_exceeds."""

from decimal import Decimal

from playwright.sync_api import Page
import pytest

from tests.component.fakeshop import BASE, FakeShop
from shop.artifacts import RunArtifacts
from shop.models import CartEntry
from shop.pages import CartPage
from shop.workflow import ShoppingWorkflow

pytestmark = pytest.mark.component

ROWS = [
    {
        "slug": "build-your-own-computer",
        "title": "Build your own computer",
        "unit_price": "1,215.00",
        "quantity": 1,
        "line_total": "1,215.00",
        "attributes": "Processor: 2.5 GHz [+15.00]<br>HDD: 320 GB",
    },
    {"slug": "blue-jeans", "title": "Blue Jeans", "unit_price": "1.00", "quantity": 3, "line_total": "3.00"},
]


def one_row(price: str) -> list[dict[str, object]]:
    return [{"slug": "thing", "title": "Thing", "unit_price": price, "quantity": 1, "line_total": price}]


def test_reads_rows_and_sub_total_with_thousands_separator(page: Page, shop: FakeShop) -> None:
    shop.cart(ROWS, sub_total="1,218.00", total="1,230.50")
    cart = CartPage(page, BASE).open()

    snapshot = cart.snapshot()

    assert snapshot.sub_total == Decimal("1218.00")
    assert snapshot.entries == [
        CartEntry(
            "Build your own computer",
            1,
            Decimal("1215.00"),
            Decimal("1215.00"),
            {"Processor": "2.5 GHz [+15.00]", "HDD": "320 GB"},
        ),
        CartEntry("Blue Jeans", 3, Decimal("1.00"), Decimal("3.00")),
    ]
    assert snapshot.quantity == 4
    assert cart.totals.total() == Decimal("1230.50")  # 'Total:' is not confused with 'Sub-Total:'
    assert not cart.is_empty()


def test_attributes_as_the_live_cart_lists_them(page: Page, shop: FakeShop) -> None:
    # Copied from the live cart: one line per attribute, a ticked checkbox per line, gift card From/For lines.
    attributes = (
        "\n Processor: 2.2 GHz Intel Pentium Dual-Core E2200<br>RAM: 8GB [+60.00]"
        "<br>Software: Microsoft Office  [+50.00]<br>Software: Acrobat Reader [+10.00]"
        "<br>From: QA Tester &lt;qa@example.com&gt;\n "
    )
    shop.cart([{**one_row("1.00")[0], "attributes": attributes}], sub_total="1.00")

    [entry] = CartPage(page, BASE).open().snapshot().entries

    assert entry.attributes == {
        "Processor": "2.2 GHz Intel Pentium Dual-Core E2200",
        "RAM": "8GB [+60.00]",
        "Software": "Microsoft Office [+50.00], Acrobat Reader [+10.00]",
        "From": "QA Tester <qa@example.com>",
    }


def test_empty_cart_is_zero(page: Page, shop: FakeShop) -> None:
    shop.cart([], sub_total="")
    cart = CartPage(page, BASE).open()
    assert cart.is_empty()
    assert cart.sub_total() == Decimal("0")
    assert cart.snapshot().entries == []


@pytest.mark.parametrize(
    ("sub_total", "budget", "count"),
    [
        ("1,000.00", Decimal("500"), 2),  # equal to the threshold
        ("999.99", Decimal("500"), 2),
        ("999.99", 333.33, 3),  # float budget: 333.33 x 3 = 999.99 exactly
        ("1,500.00", "1500.00", 1),  # str budget
    ],
)
def test_assertion_passes_up_to_the_threshold(
    page: Page, shop: FakeShop, artifacts: RunArtifacts, sub_total: str, budget, count: int
) -> None:
    shop.cart(one_row(sub_total), sub_total=sub_total)
    cart = ShoppingWorkflow(page, BASE, artifacts).assert_cart_total_not_exceeds(budget, count)
    assert cart.sub_total == Decimal(sub_total.replace(",", ""))
    assert list(artifacts.directory.glob("*-cart.png"))


@pytest.mark.parametrize(
    ("sub_total", "budget", "count"),
    [
        ("1,000.01", Decimal("500"), 2),  # 0.01 over
        ("1,000.00", 333.33, 3),  # 0.01 over 999.99
        ("0.01", Decimal("0"), 5),  # zero budget
        ("10.00", Decimal("100"), 0),  # no items expected but the cart is not empty
    ],
)
def test_assertion_fails_when_over_the_threshold(
    page: Page, shop: FakeShop, artifacts: RunArtifacts, sub_total: str, budget, count: int
) -> None:
    shop.cart(one_row(sub_total), sub_total=sub_total)
    with pytest.raises(AssertionError, match="exceeds"):
        ShoppingWorkflow(page, BASE, artifacts).assert_cart_total_not_exceeds(budget, count)
    assert list(artifacts.directory.glob("*-cart.png"))  # screenshot taken before the assertion


def test_assertion_on_empty_cart_with_zero_items(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.cart([], sub_total="")
    cart = ShoppingWorkflow(page, BASE, artifacts).assert_cart_total_not_exceeds(Decimal("100"), 0)
    assert cart.sub_total == Decimal("0")
