"""Paging guard (max_pages / MAX_PAGES), pages read (SearchOutcome.pages), and the advanced search options
(price filter, 'Search In product descriptions') as submitted by the real form."""

from decimal import Decimal
import logging
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page
import pytest

from tests.component.fakeshop import BASE, Card, FakeShop, grid_html
from shop.artifacts import RunArtifacts
from shop.collector import ProductCollector
from shop.models import SearchOutcome
from shop.pages import CategoryPage, ListingPage, SearchPage
from shop.workflow import ShoppingWorkflow

pytestmark = pytest.mark.component


def cards(prefix: str, *prices: str) -> list[Card]:
    return [Card(f"{prefix} {index}", price) for index, price in enumerate(prices, start=1)]


def collect(listing: ListingPage, max_price: str, limit: int, max_pages: int | None = None) -> SearchOutcome:
    return ProductCollector(listing.grid, listing.pager).collect(Decimal(max_price), limit, max_pages)


# ------------------------------------------------------------- max_pages guard


def test_max_pages_parameter_stops_an_endless_pager(page: Page, shop: FakeShop, caplog) -> None:
    shop.endless_category("endless", price="999.00")
    listing = CategoryPage(page, BASE, "endless").open()

    with caplog.at_level(logging.WARNING):
        outcome = collect(listing, "10", limit=5, max_pages=3)

    assert outcome.products == []
    assert outcome.pages == [1, 2, 3]
    assert len(shop.page_requests("/endless")) == 3  # page 4 never requested
    assert listing.pager.has_next()  # it stopped because of the guard, not because the pages ended
    assert "max_pages" in caplog.text


def test_default_max_pages_is_twenty(page: Page, shop: FakeShop) -> None:
    shop.endless_category("endless", price="999.00")
    listing = CategoryPage(page, BASE, "endless").open()

    outcome = collect(listing, "10", limit=5)
    assert outcome.products == []
    assert ProductCollector.MAX_PAGES == 20
    assert outcome.pages == list(range(1, 21))


def test_guard_keeps_what_was_found(page: Page, shop: FakeShop) -> None:
    shop.endless_category("endless", price="1.00")  # one cheap item per page
    listing = CategoryPage(page, BASE, "endless").open()
    found = collect(listing, "10", limit=10, max_pages=4).products
    assert [item.title for item in found] == ["Item 1", "Item 2", "Item 3", "Item 4"]


def test_max_pages_one_reads_only_the_first_page(page: Page, shop: FakeShop) -> None:
    shop.category("notebooks", [cards("A", "1.00"), cards("B", "1.00")])
    listing = CategoryPage(page, BASE, "notebooks").open()
    outcome = collect(listing, "10", limit=5, max_pages=1)
    assert len(outcome.products) == 1
    assert outcome.pages == [1]


def test_max_pages_class_attribute_override_is_honoured(
    page: Page, shop: FakeShop, monkeypatch: pytest.MonkeyPatch
) -> None:
    shop.endless_category("endless", price="999.00")
    monkeypatch.setattr(ProductCollector, "MAX_PAGES", 2)
    listing = CategoryPage(page, BASE, "endless").open()
    assert collect(listing, "10", limit=5).pages == [1, 2]


def test_next_pointing_back_to_a_read_page_stops_cleanly(page: Page, shop: FakeShop, caplog) -> None:
    # A broken pager: page 2's Next links back to page 1. Following it would loop (or time out waiting for
    # page 3), so the collection stops and logs instead.
    def body(query: dict[str, list[str]]) -> str:
        number = int(query.get("pagenumber", ["1"])[0])
        target = 2 if number == 1 else 1
        pager = (
            f'<div class="pager"><ul><li class="current-page"><span>{number}</span></li>'
            f'<li class="next-page"><a href="/loop?pagenumber={target}">Next</a></li></ul></div>'
        )
        return f'<div class="page-body">{grid_html(cards(f"P{number}", "1.00"))}{pager}</div>'

    shop.html("/loop", body)
    listing = CategoryPage(page, BASE, "loop").open()
    with caplog.at_level(logging.WARNING):
        outcome = collect(listing, "10", limit=5)
    assert [item.title for item in outcome.products] == ["P1 1", "P2 1"]
    assert outcome.pages == [1, 2]
    assert "already read" in caplog.text


# ------------------------------------------------------------- pages read


def test_visited_pages_when_limit_reached_on_page_two(page: Page, shop: FakeShop) -> None:
    shop.category("notebooks", [cards("A", "1.00"), cards("B", "1.00", "1.00"), cards("C", "1.00")])
    listing = CategoryPage(page, BASE, "notebooks").open()
    assert collect(listing, "10", limit=2).pages == [1, 2]


def test_visited_pages_start_where_the_listing_is(page: Page, shop: FakeShop) -> None:
    shop.category("notebooks", [cards("A", "1.00"), cards("B", "1.00"), cards("C", "1.00")])
    page.goto(f"{BASE}/notebooks?pagenumber=2")
    listing = CategoryPage(page, BASE, "notebooks")
    assert collect(listing, "10", limit=5).pages == [2, 3]


def test_visited_pages_reset_on_each_collection(page: Page, shop: FakeShop) -> None:
    shop.category("notebooks", [cards("A", "1.00"), cards("B", "1.00")])
    listing = CategoryPage(page, BASE, "notebooks").open()
    assert collect(listing, "10", limit=5).pages == [1, 2]
    assert collect(listing.open(), "10", limit=1).pages == [1]  # each outcome only lists its own pages


def test_visited_pages_for_zero_results_and_limit_zero(page: Page, shop: FakeShop) -> None:
    shop.category("empty", [])
    listing = CategoryPage(page, BASE, "empty").open()
    assert collect(listing, "10", limit=5) == SearchOutcome([], [1])
    assert collect(listing, "10", limit=0) == SearchOutcome([], [])


# ------------------------------------------------------------- search form options


def submitted(shop: FakeShop) -> dict[str, list[str]]:
    entries = [entry for entry in shop.page_requests("/search") if "Q=" in entry]
    assert len(entries) == 1, shop.requests
    return parse_qs(urlsplit(entries[0].split(" ", 1)[1]).query, keep_blank_values=True)


def test_workflow_search_in_descriptions_sends_sid_and_as(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([cards("Book", "5.00")])
    ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price(
        "the", Decimal("50"), 5, in_descriptions=True
    )
    query = submitted(shop)
    assert query["Q"] == ["the"]
    assert "true" in query["As"]
    assert "true" in query["Sid"]
    assert query["Pt"] == ["50.00"]
    assert artifacts.events[-1]["in_descriptions"] is True


def test_workflow_default_does_not_search_descriptions(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([cards("Book", "5.00")])
    ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price("book", Decimal("50"), 5)
    query = submitted(shop)
    assert query["Sid"] == ["false"]  # only the hidden companion input
    assert "true" in query["As"]  # still advanced: the price filter needs it


def test_descriptions_without_price_uses_advanced_search(page: Page, shop: FakeShop) -> None:
    shop.search([cards("Book", "5.00")])
    SearchPage(page, BASE).open().search("book", None, in_descriptions=True)
    query = submitted(shop)
    assert "true" in query["As"] and "true" in query["Sid"]
    assert query["Pt"] == [""]


def test_plain_search_leaves_advanced_off(page: Page, shop: FakeShop) -> None:
    shop.search([cards("Book", "5.00")])
    SearchPage(page, BASE).open().search("book")
    query = submitted(shop)
    assert query["As"] == ["false"] and query["Sid"] == ["false"]


def test_form_without_descriptions_option_still_searches(
    page: Page, shop: FakeShop, artifacts: RunArtifacts, caplog
) -> None:
    shop.search([cards("Book", "5.00", "80.00")], descriptions_option=False)
    with caplog.at_level(logging.WARNING):
        urls = ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price(
            "book", Decimal("50"), 5, in_descriptions=True
        )
    assert urls == [f"{BASE}/book-1"]
    query = submitted(shop)
    assert "Sid" not in query and query["Pt"] == ["50.00"]
    assert "Search In product descriptions" in caplog.text


def test_form_without_advanced_block_ignores_descriptions(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    shop.search([cards("Book", "5.00", "80.00")], price_filter=False)
    urls = ShoppingWorkflow(page, BASE, artifacts).search_items_by_name_under_price(
        "book", Decimal("50"), 5, in_descriptions=True
    )
    assert urls == [f"{BASE}/book-1"]
    query = submitted(shop)
    assert "As" not in query and "Sid" not in query
