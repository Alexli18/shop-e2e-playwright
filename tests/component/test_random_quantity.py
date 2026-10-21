"""Opt-in random quantity (a case's max_quantity > 1): a seeded quantity 1..max per item is typed into the
product page's Qty field and posted; with the default (1) nothing changes, not even the random options."""

from decimal import Decimal

from playwright.sync_api import Page
import pytest

from shop.artifacts import RunArtifacts
from shop.models import AddStatus
from shop.workflow import ShoppingWorkflow
from tests.component.catalog import BYOC, LAPTOP
from tests.component.fakeshop import BASE, Card, FakeShop

pytestmark = pytest.mark.component


def open_search_tab(page: Page, shop: FakeShop) -> None:
    shop.search([[Card("Anything", "1.00")]])
    page.goto(f"{BASE}/search?q=anything")


def posted_quantities(shop: FakeShop) -> list[int]:
    return [
        int(next(values[0] for name, values in form.items() if name.endswith(".EnteredQuantity")))
        for _slug, form in shop.added
    ]


def test_quantities_are_random_within_the_limit_and_posted(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    open_search_tab(page, shop)
    urls = [shop.product(LAPTOP), shop.product(BYOC)] * 3

    items = ShoppingWorkflow(page, BASE, artifacts, seed=4, max_quantity=3).add_items_to_cart(urls)

    assert [item.status for item in items] == [AddStatus.ADDED] * 6
    quantities = [item.quantity for item in items]
    assert all(1 <= quantity <= 3 for quantity in quantities)
    assert len(set(quantities)) > 1  # really random, not always the same value
    assert posted_quantities(shop) == quantities  # what the shop received
    assert [item.page_price for item in items] == [Decimal("1590.00"), Decimal("1200.00")] * 3


def test_same_seed_same_quantities(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    open_search_tab(page, shop)
    urls = [shop.product(LAPTOP)] * 4
    first = ShoppingWorkflow(page, BASE, artifacts, seed=21, max_quantity=5).add_items_to_cart(urls)
    second = ShoppingWorkflow(page, BASE, artifacts, seed=21, max_quantity=5).add_items_to_cart(urls)
    assert [item.quantity for item in first] == [item.quantity for item in second]


def test_default_is_one_unit_and_keeps_the_option_choices(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    open_search_tab(page, shop)
    url = shop.product(BYOC)
    default = ShoppingWorkflow(page, BASE, artifacts, seed=99).add_items_to_cart([url, url])
    explicit = ShoppingWorkflow(page, BASE, artifacts, seed=99, max_quantity=1).add_items_to_cart([url, url])

    assert [item.quantity for item in default] == [1, 1]
    assert posted_quantities(shop) == [1, 1, 1, 1]
    # max_quantity 1 does not draw from the RNG, so the option choices are the ones the assignment runs make.
    assert [item.options for item in default] == [item.options for item in explicit]
