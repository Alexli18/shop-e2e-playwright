"""SearchOutcome / RunResult.search, authenticate() and the whole ShoppingWorkflow.run() on the fake shop."""

from decimal import Decimal
import json

from playwright.sync_api import Page
import pytest

from tests.component.catalog import BYOC
from tests.component.fakeshop import BASE, Card, FakeShop, Product
from shop.artifacts import RunArtifacts
from shop.config import Credentials
from shop.models import AddStatus, ProductSummary, SearchOutcome, ShoppingCase
from shop.workflow import ShoppingWorkflow

pytestmark = pytest.mark.component

CHEAP = Product("cheap-computer", 101, "Cheap computer", price="800.00")
GIFT = Product("gift-card", 102, "Gift card", price="10.00", stock=None, giftcard="virtual")
PAGES = [
    [Card("Cheap computer", "800.00"), Card("Expensive computer", "1,600.00", old_price="1,900.00")],
    [Card("Build your own computer", "1,200.00"), Card("Gift card", "10.00"), Card("Spare", "5.00")],
]


# ------------------------------------------------------------- SearchOutcome


def test_last_search_holds_products_with_prices_and_pages(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search(PAGES)
    workflow = ShoppingWorkflow(page, BASE, artifacts)

    urls = workflow.search_items_by_name_under_price("computer", Decimal("1500"), limit=3)

    assert workflow.last_search == SearchOutcome(
        products=[
            ProductSummary("Cheap computer", f"{BASE}/cheap-computer", Decimal("800.00")),
            ProductSummary("Build your own computer", f"{BASE}/build-your-own-computer", Decimal("1200.00")),
            ProductSummary("Gift card", f"{BASE}/gift-card", Decimal("10.00")),
        ],
        pages=[1, 2],
    )
    assert urls == [product.url for product in workflow.last_search.products]
    assert artifacts.events[-1]["pages"] == [1, 2]


@pytest.mark.parametrize(
    ("pages", "limit", "expected_pages"),
    [
        ([], 5, [1]),  # 'No products were found': one page read
        (PAGES, 0, []),  # limit 0: nothing searched
        (PAGES, 1, [1]),
    ],
)
def test_last_search_edge_cases(
    page: Page, shop: FakeShop, artifacts: RunArtifacts, pages, limit: int, expected_pages: list[int]
) -> None:
    shop.search(pages)
    workflow = ShoppingWorkflow(page, BASE, artifacts)
    urls = workflow.search_items_by_name_under_price("computer", Decimal("1500"), limit)
    assert workflow.last_search.pages == expected_pages
    assert [product.url for product in workflow.last_search.products] == urls


def test_last_search_is_reset_by_the_next_search(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search(PAGES)
    workflow = ShoppingWorkflow(page, BASE, artifacts)
    workflow.search_items_by_name_under_price("computer", Decimal("1500"), 3)
    workflow.search_items_by_name_under_price("computer", Decimal("1500"), 0)
    assert workflow.last_search == SearchOutcome([], [])


# ------------------------------------------------------------- authenticate / run


def test_authenticate_registers_logs_out_and_back_in(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.accounts_pages()

    email = ShoppingWorkflow(page, BASE, artifacts).authenticate()

    assert shop.logged_in == email and email in shop.accounts
    assert [
        entry.split("?")[0] for entry in shop.requests if entry.split(" ")[1] in ("/register", "/login", "/logout")
    ] == ["GET /register", "POST /register", "GET /logout", "GET /login", "POST /login"]
    log_text = json.dumps(artifacts.events, default=str)
    assert email in log_text and shop.accounts[email] not in log_text  # the password is never logged


def test_authenticate_with_existing_account(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.accounts_pages()
    shop.live_cart()
    shop.accounts["known@example.com"] = "Secret-123"

    email = ShoppingWorkflow(
        page, BASE, artifacts, credentials=Credentials("known@example.com", "Secret-123")
    ).authenticate()

    assert email == shop.logged_in == "known@example.com"
    assert not any("/register" in entry for entry in shop.requests)
    assert "GET /cart" in shop.requests  # the old cart is checked (empty here, so nothing to clear)


def test_run_returns_search_outcome_items_and_cart(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.accounts_pages()
    shop.search(PAGES)
    for product in (CHEAP, BYOC, GIFT):
        shop.product(product)
    shop.live_cart()
    case = ShoppingCase(
        "offline-run",
        "computer",
        Decimal("1500.00"),
        limit=3,
        seed=7,
        search_in_descriptions=True,
        min_results=3,
        min_search_pages=2,
    )

    result = ShoppingWorkflow(page, BASE, artifacts).run(case)

    assert result.urls == [f"{BASE}/cheap-computer", f"{BASE}/build-your-own-computer", f"{BASE}/gift-card"]
    assert result.search.pages == [1, 2]
    assert [product.price for product in result.search.products] == [
        Decimal("800.00"),
        Decimal("1200.00"),
        Decimal("10.00"),
    ]
    assert all(product.price <= case.max_price for product in result.search.products)
    assert [item.status for item in result.items] == [AddStatus.ADDED] * 3, [i.message for i in result.items]
    assert "HDD" in result.items[1].options
    assert result.items[2].text_fields["Recipient's Name"] == "QA Tester"
    assert result.cart.sub_total == Decimal("2010.00")
    assert result.cart.quantity == 3
    assert any("Sid=true" in entry for entry in shop.page_requests("/search"))  # search_in_descriptions
    assert [event["event"] for event in artifacts.events][:3] == ["case", "authenticated", "search"]


def test_run_with_empty_search_checks_an_empty_cart(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.accounts_pages()
    shop.search([])
    shop.live_cart()
    case = ShoppingCase("no-results", "zzzzqqq", Decimal("100"), limit=5, seed=1, expect_empty=True)

    result = ShoppingWorkflow(page, BASE, artifacts).run(case)

    assert result.urls == [] and result.items == []
    assert result.search == SearchOutcome([], [1])
    assert result.cart.sub_total == Decimal("0")
