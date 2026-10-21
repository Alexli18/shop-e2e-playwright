"""Search / listing collection (ProductCollector, ProductGrid, ProductCard, Pager)
and the workflow's search_items_by_name_under_price, against routed fixture pages."""

from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page
import pytest

from tests.component.fakeshop import BASE, Card, FakeShop, fixture, grid_html, render
from shop.artifacts import RunArtifacts
from shop.collector import ProductCollector
from shop.components import Pager
from shop.pages import CategoryPage, SearchPage
from shop.workflow import ShoppingWorkflow

pytestmark = pytest.mark.component

SLUG = "notebooks"


def cards(prefix: str, *prices: str) -> list[Card]:
    return [Card(f"{prefix} {index}", price) for index, price in enumerate(prices, start=1)]


def collect(page: Page, shop: FakeShop, pages: list[list[Card]], max_price: str, limit: int) -> list:
    shop.category(SLUG, pages)
    listing = CategoryPage(page, BASE, SLUG).open()
    return ProductCollector(listing.grid, listing.pager).collect(Decimal(max_price), limit).products


def listing_requests(shop: FakeShop) -> list[str]:
    return shop.page_requests(f"/{SLUG}")


# ------------------------------------------------------------- price filter and limit


def test_items_above_max_price_are_excluded(page: Page, shop: FakeShop) -> None:
    pages = [
        [
            Card("Cheap", "10.00"),
            Card("Exact", "100.00"),
            Card("Pricey", "100.01"),
            Card("Big", "1,590.00"),
            Card("Also cheap", "99.99"),
        ]
    ]
    found = collect(page, shop, pages, "100.00", limit=5)
    assert [item.title for item in found] == ["Cheap", "Exact", "Also cheap"]
    assert [item.price for item in found] == [Decimal("10.00"), Decimal("100.00"), Decimal("99.99")]


def test_exactly_limit_returned_without_paging(page: Page, shop: FakeShop) -> None:
    pages = [cards("A", *["5.00"] * 8), cards("B", "1.00", "1.00")]
    found = collect(page, shop, pages, "10", limit=5)
    assert [item.title for item in found] == ["A 1", "A 2", "A 3", "A 4", "A 5"]
    assert listing_requests(shop) == [f"GET /{SLUG}"]  # enough on page 1: Next not followed


def test_fewer_than_limit_follows_next_across_three_pages(page: Page, shop: FakeShop) -> None:
    pages = [cards("P1", "5.00", "500.00"), cards("P2", "600.00", "6.00"), cards("P3", "7.00", "8.00", "9.00")]
    found = collect(page, shop, pages, "10.00", limit=4)
    assert [item.title for item in found] == ["P1 1", "P2 2", "P3 1", "P3 2"]
    assert listing_requests(shop) == [f"GET /{SLUG}", f"GET /{SLUG}?pagenumber=2", f"GET /{SLUG}?pagenumber=3"]
    assert Pager(page).current_page() == 3


def test_stops_on_the_page_where_limit_is_reached(page: Page, shop: FakeShop) -> None:
    pages = [cards("P1", "1.00"), cards("P2", "2.00", "3.00", "4.00"), cards("P3", "5.00")]
    found = collect(page, shop, pages, "10", limit=3)
    assert [item.title for item in found] == ["P1 1", "P2 1", "P2 2"]
    assert f"GET /{SLUG}?pagenumber=3" not in shop.requests


def test_stops_when_there_is_no_next_page(page: Page, shop: FakeShop) -> None:
    pages = [cards("P1", "1.00", "99.00"), cards("P2", "2.00")]
    found = collect(page, shop, pages, "10", limit=5)
    assert [item.title for item in found] == ["P1 1", "P2 1"]
    assert listing_requests(shop) == [f"GET /{SLUG}", f"GET /{SLUG}?pagenumber=2"]
    assert not Pager(page).has_next()


def test_nothing_under_price_on_any_page_returns_empty(page: Page, shop: FakeShop) -> None:
    pages = [cards("P1", "50.00"), cards("P2", "60.00")]
    assert collect(page, shop, pages, "10", limit=5) == []
    assert len(listing_requests(shop)) == 2


def test_duplicates_across_pages_are_deduplicated(page: Page, shop: FakeShop) -> None:
    # Live listings shift while paging (shared demo data): page 2 repeats a product from page 1.
    a, b, c, d = Card("A", "1.00"), Card("B", "2.00"), Card("C", "3.00"), Card("D", "4.00")
    found = collect(page, shop, [[a, b], [b, c, a], [d]], "10", limit=4)
    assert [item.title for item in found] == ["A", "B", "C", "D"]
    assert len({item.url for item in found}) == 4


def test_discounted_item_uses_actual_price_not_old_price(page: Page, shop: FakeShop) -> None:
    pages = [
        [Card("On sale", "1,200.00", old_price="1,500.00"), Card("Fake discount", "1,400.00", old_price="1,100.00")]
    ]
    found = collect(page, shop, pages, "1300", limit=5)
    assert [(item.title, item.price) for item in found] == [("On sale", Decimal("1200.00"))]


def test_card_with_unreadable_price_is_skipped(page: Page, shop: FakeShop) -> None:
    found = collect(page, shop, [[Card("Call me", "Call for pricing"), Card("Normal", "3.00")]], "10", limit=5)
    assert [item.title for item in found] == ["Normal"]


def test_card_without_price_element_is_skipped(page: Page, shop: FakeShop) -> None:
    page.set_default_timeout(1000)
    found = collect(page, shop, [[Card("No price", None), Card("Normal", "3.00")]], "10", limit=5)
    assert [item.title for item in found] == ["Normal"]


def test_limit_zero_collects_nothing(page: Page, shop: FakeShop) -> None:
    assert collect(page, shop, [cards("A", "1.00")], "10", limit=0) == []


def test_urls_are_absolute(page: Page, shop: FakeShop) -> None:
    found = collect(page, shop, [[Card("Simple Computer", "800.00")]], "1000", limit=1)
    assert found[0].url == f"{BASE}/simple-computer"


# ------------------------------------------------------------- pager


def test_single_page_pager_is_empty_like_the_live_search(page: Page, shop: FakeShop) -> None:
    shop.category(SLUG, [cards("A", "1.00")])
    CategoryPage(page, BASE, SLUG).open()
    pager = Pager(page)
    assert not pager.has_next()
    assert pager.current_page() == 1
    assert pager.go_next() is False


def test_pager_next_on_middle_page(page: Page, shop: FakeShop) -> None:
    shop.category(SLUG, [cards("A", "1"), cards("B", "1"), cards("C", "1")])
    page.goto(f"{BASE}/{SLUG}?pagenumber=2")
    pager = Pager(page)
    assert pager.current_page() == 2  # 'Previous' and page links do not confuse it
    assert pager.go_next() is True
    assert pager.current_page() == 3
    assert pager.go_next() is False


# ------------------------------------------------------------- the workflow function (search form)


def search_query(shop: FakeShop) -> dict[str, list[str]]:
    """Query string of the form submission (the first /search request carrying Q)."""
    submitted = [entry for entry in shop.page_requests("/search") if "Q=" in entry]
    assert submitted, shop.requests
    return parse_qs(urlsplit(submitted[0].split(" ", 1)[1]).query, keep_blank_values=True)


def test_workflow_uses_price_filter_and_returns_urls(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    # The shop's own filter is not trusted: the 'server' still returns an item above the limit.
    shop.search(
        [
            [
                Card("Build your own cheap computer", "800.00"),
                Card("Build your own computer", "1,200.00"),
                Card("Expensive computer", "1,500.01"),
                Card("Simple Computer", "800.00"),
            ]
        ]
    )
    workflow = ShoppingWorkflow(page, BASE, artifacts)

    urls = workflow.search_items_by_name_under_price("computer", Decimal("1500"), limit=5)

    assert urls == [
        f"{BASE}/build-your-own-cheap-computer",
        f"{BASE}/build-your-own-computer",
        f"{BASE}/simple-computer",
    ]
    query = search_query(shop)
    assert query["Q"] == ["computer"]
    assert "true" in query["As"]
    assert query["Pt"] == ["1500.00"]
    assert query["Pf"] == [""]
    assert list(artifacts.directory.glob("*search-computer.png"))
    assert artifacts.events[-1]["event"] == "search"


def test_workflow_without_price_filter_on_page_filters_itself(
    page: Page, shop: FakeShop, artifacts: RunArtifacts
) -> None:
    shop.search([[Card("Phone A", "100.00"), Card("Phone B", "600.00"), Card("Phone C", "500.00")]], price_filter=False)
    urls = ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price("phone", Decimal("500"), 5)
    assert urls == [f"{BASE}/phone-a", f"{BASE}/phone-c"]
    query = search_query(shop)
    assert "Pt" not in query and "As" not in query


def test_workflow_search_follows_next_page(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([cards("Shoe", "10.00", "50.00", "11.00"), cards("Boot", "12.00", "13.00", "14.00")])
    urls = ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price("shoe", Decimal("20"), limit=4)
    assert urls == [f"{BASE}/shoe-1", f"{BASE}/shoe-3", f"{BASE}/boot-1", f"{BASE}/boot-2"]
    assert any("pagenumber=2" in entry for entry in shop.page_requests("/search"))


def test_workflow_zero_results(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([])
    assert ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price("zzzzqqq", Decimal("100")) == []


def test_zero_cards_without_the_result_message_is_a_markup_error(page: Page, shop: FakeShop) -> None:
    # A theme change: the cards are there, but the grid class is new, so the card XPath matches nothing.
    results = grid_html([Card("Laptop", "90.00")]).replace("product-grid", "product-tiles")
    form = fixture("search_form.html")
    shop.html("/search", lambda query: render(form, query="", advanced_toggle="", advanced_block="", results=(
        f'<div class="search-results">{results}</div>' if "Q" in query else ""
    )))  # fmt: skip
    with pytest.raises(AssertionError, match="has the markup changed"):
        SearchPage(page, BASE).open().search("laptop")


def test_workflow_limit_zero_does_not_search(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([cards("A", "1.00")])
    assert ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price("abc", Decimal("10"), 0) == []
    assert shop.requests == []


def test_workflow_default_limit_is_five(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([cards("Item", *["1.00"] * 7)])
    urls = ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price("item", Decimal("10"))
    assert len(urls) == 5


def test_search_page_accepts_float_and_str_price(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([[Card("Book", "19.99"), Card("Book 2", "20.00")]])
    urls = ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price("book", 19.99, 5)
    assert urls == [f"{BASE}/book"]
    assert search_query(shop)["Pt"] == ["19.99"]


def test_search_page_object_directly(page: Page, shop: FakeShop) -> None:
    shop.search([[Card("Laptop", "1590.00")]])
    results = SearchPage(page, BASE).open().search("laptop", Decimal("2000"))
    assert [item.title for item in results.grid.summaries()] == ["Laptop"]
