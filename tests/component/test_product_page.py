"""ProductPage / Notification add-to-cart outcomes and the workflow's add_items_to_cart."""

from decimal import Decimal
import random

from playwright.sync_api import Page
import pytest

from tests.component.catalog import (
    BYOC,
    CHECKBOXES_REQUIRED,
    GIFT_CARD,
    LAPTOP,
    NEEDS_HIDDEN_OPTION,
    NO_PURCHASE_BLOCK,
    NOT_SOLD,
    OUT_OF_STOCK,
    RENAMED_BUTTON,
    SOLD_OUT_ON_CLICK,
    WISHLIST_ONLY,
)
from tests.component.fakeshop import BASE, Card, FakeShop
from shop.artifacts import RunArtifacts
from shop.models import AddStatus
from shop.pages import ProductPage
from shop.workflow import ShoppingWorkflow

pytestmark = pytest.mark.component

SUCCESS_TEXT = "The product has been added to your shopping cart"


def open_product(page: Page, url: str) -> ProductPage:
    return ProductPage(page, BASE).open_url(url)


def test_title_and_price_come_from_the_main_product_block(page: Page, shop: FakeShop) -> None:
    product = open_product(page, shop.product(BYOC))
    assert product.title() == "Build your own computer"
    assert product.price() == Decimal("1200.00")
    assert product.availability() == "In stock"


def test_success_bar(page: Page, shop: FakeShop) -> None:
    product = open_product(page, shop.product(LAPTOP))
    assert product.unavailable_reason() is None

    notice = product.add_to_cart()

    assert notice.success is True
    assert notice.text == SUCCESS_TEXT
    assert product.header.cart_quantity() == 1
    assert shop.requests.count("POST /addproducttocart/details/31/1") == 1  # main button, not a related tile


def test_error_bar_when_required_option_missing(page: Page, shop: FakeShop) -> None:
    notice = open_product(page, shop.product(BYOC)).add_to_cart()
    assert notice.success is False
    assert notice.text == "Please select HDD"
    assert shop.cart_count == 0


def test_required_option_chosen_then_added(page: Page, shop: FakeShop) -> None:
    product = open_product(page, shop.product(BYOC))
    product.options.choose_randomly(random.Random(5))
    assert product.add_to_cart().success


def test_second_add_on_the_same_page_reads_the_new_outcome(page: Page, shop: FakeShop) -> None:
    # The error bar of the first click stays visible; the second outcome must not be read from it.
    product = open_product(page, shop.product(BYOC))
    assert product.add_to_cart().text == "Please select HDD"
    product.options.choose_randomly(random.Random(5))

    notice = product.add_to_cart()

    assert notice.success is True, notice.text
    assert shop.cart_count == 1


def test_error_bar_with_several_messages(page: Page, shop: FakeShop) -> None:
    notice = open_product(page, shop.product(GIFT_CARD)).add_to_cart()
    assert notice.success is False
    assert notice.text == (
        "Enter valid recipient name Enter valid recipient email Enter valid sender name Enter valid sender email"
    )


@pytest.mark.parametrize(
    ("product", "reason"),
    [
        (NOT_SOLD, "Not sold online (empty purchase block)"),
        (WISHLIST_ONLY, "Wishlist only (no Add to cart)"),
        (OUT_OF_STOCK, "Out of stock"),
        (LAPTOP, None),
        (GIFT_CARD, None),  # no stock block at all
    ],
    ids=["not-sold", "wishlist-only", "out-of-stock", "in-stock", "no-stock-info"],
)
def test_unavailable_reason(page: Page, shop: FakeShop, product, reason) -> None:
    assert open_product(page, shop.product(product)).unavailable_reason() == reason


@pytest.mark.parametrize(
    "product", [RENAMED_BUTTON, NO_PURCHASE_BLOCK], ids=["button-says-add-to-basket", "no-purchase-block"]
)
def test_changed_markup_fails_instead_of_skipping_the_product(
    page: Page, shop: FakeShop, artifacts: RunArtifacts, product
) -> None:
    # Skipping it as 'unavailable' would leave the cart empty, and an empty cart always passes the budget check.
    open_search_tab(page, shop)
    with pytest.raises(AssertionError, match="has the markup changed"):
        ShoppingWorkflow(page, BASE, artifacts, seed=1).add_items_to_cart([shop.product(product)])


# ------------------------------------------------------------- workflow.add_items_to_cart


def open_search_tab(page: Page, shop: FakeShop) -> str:
    shop.search([[Card("Anything", "1.00")]])
    page.goto(f"{BASE}/search?q=anything")
    return page.url


def test_add_items_to_cart_statuses_tab_and_artifacts(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    search_url = open_search_tab(page, shop)
    urls = [
        shop.product(product)
        for product in (LAPTOP, BYOC, NOT_SOLD, OUT_OF_STOCK, SOLD_OUT_ON_CLICK, NEEDS_HIDDEN_OPTION)
    ]

    items = ShoppingWorkflow(page, BASE, artifacts, seed=11).add_items_to_cart(urls)

    assert [item.status for item in items] == [
        AddStatus.ADDED,
        AddStatus.ADDED,
        AddStatus.UNAVAILABLE,
        AddStatus.UNAVAILABLE,
        AddStatus.UNAVAILABLE,
        AddStatus.REJECTED,
    ]
    assert [item.url for item in items] == urls
    assert items[0].options == {} and items[0].message == SUCCESS_TEXT
    assert set(items[1].options) == {"Processor", "RAM", "HDD", "OS", "Software"}  # Software: the ticked default
    assert items[1].options["Software"] == "Microsoft Office [+50.00]"
    assert items[2].message == "Not sold online (empty purchase block)"
    assert items[4].message == "Out of stock"
    assert items[5].message == "Please select Color"
    assert shop.cart_count == 2
    # Back on the search tab: product tabs were closed and the results page never navigated away.
    assert page.context.pages == [page]
    assert page.url == search_url
    assert page.locator(".search-results .product-item").count() == 1
    # One screenshot and one log event per item.
    assert len(list(artifacts.directory.glob("*.png"))) == len(urls)
    events = [event for event in artifacts.events if event["event"] == "add_to_cart"]
    assert [event["cart_counter"] for event in events] == [1, 2, 2, 2, 2, 2]


def test_add_items_to_cart_is_reproducible_for_a_seed(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    open_search_tab(page, shop)
    url = shop.product(BYOC)
    first = ShoppingWorkflow(page, BASE, artifacts, seed=99).add_items_to_cart([url])
    second = ShoppingWorkflow(page, BASE, artifacts, seed=99).add_items_to_cart([url])
    assert first[0].options == second[0].options


def test_add_items_to_cart_with_no_urls(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    assert ShoppingWorkflow(page, BASE, artifacts).add_items_to_cart([]) == []


def test_multi_message_refusal_is_rejected_not_a_crash(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    # Two required checkbox groups: the chooser does not tick checkboxes, so the shop answers with two
    # <p class="content"> messages. The item must be REJECTED with both messages and the run must go on.
    open_search_tab(page, shop)
    urls = [shop.product(CHECKBOXES_REQUIRED), shop.product(LAPTOP)]

    items = ShoppingWorkflow(page, BASE, artifacts).add_items_to_cart(urls)

    assert [item.status for item in items] == [AddStatus.REJECTED, AddStatus.ADDED]
    assert items[0].message == "Please select Software Please select Accessories"
    logged = [event["item"] for event in artifacts.events if event["event"] == "add_to_cart"]
    assert [item.status for item in logged] == [AddStatus.REJECTED, AddStatus.ADDED]
