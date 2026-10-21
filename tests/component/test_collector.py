"""ProductCollector edge cases: limit, duplicates, guards (max_pages, Next pointing back), the pages recorded per
outcome, no state carried between collections, and grids with unreadable cards."""

from decimal import Decimal
import logging

from playwright.sync_api import Page
import pytest

from tests.component.fakeshop import BASE, Card, FakeShop, grid_html
from shop.collector import ProductCollector
from shop.models import SearchOutcome
from shop.pages import CategoryPage

pytestmark = pytest.mark.component

SKELETON_CARD = (  # a tile still loading: no title link, no price yet
    '<div class="item-box"><div class="product-item" data-productid="555">'
    '<div class="details"><h2 class="product-title"></h2><div class="add-info"><div class="prices"></div></div>'
    "</div></div></div>"
)


def collector_for(page: Page, slug: str) -> ProductCollector:
    listing = CategoryPage(page, BASE, slug)
    return ProductCollector(listing.grid, listing.pager)


def raw_listing(shop: FakeShop, slug: str, body_for_page) -> None:
    """A listing whose page-body HTML is built per page number by `body_for_page(number)`."""

    def body(query: dict[str, list[str]]) -> str:
        return f'<div class="page-body">{body_for_page(int(query.get("pagenumber", ["1"])[0]))}</div>'

    shop.html(f"/{slug}", body)


def pager(number: int, next_href: str | None) -> str:
    link = f'<li class="next-page"><a href="{next_href}">Next</a></li>' if next_href else ""
    return f'<div class="pager"><ul><li class="current-page"><span>{number}</span></li>{link}</ul></div>'


def titles(outcome: SearchOutcome) -> list[str]:
    return [product.title for product in outcome.products]


def test_duplicate_url_on_the_same_page_counts_once(page: Page, shop: FakeShop) -> None:
    same = Card("Same", "1.00")
    shop.category("dupes", [[same, Card("Other", "2.00"), same]])
    page.goto(f"{BASE}/dupes")
    outcome = collector_for(page, "dupes").collect(Decimal("10"), limit=5)
    assert titles(outcome) == ["Same", "Other"]
    assert outcome.pages == [1]


def test_exact_limit_reached_mid_page_two(page: Page, shop: FakeShop) -> None:
    shop.category("cat", [[Card("A", "1"), Card("B", "99")], [Card("C", "1"), Card("D", "1"), Card("E", "1")]])
    page.goto(f"{BASE}/cat")
    outcome = collector_for(page, "cat").collect(Decimal("10"), limit=3)
    assert titles(outcome) == ["A", "C", "D"]
    assert outcome.pages == [1, 2]


@pytest.mark.parametrize("limit", [0, -1])
def test_non_positive_limit_reads_nothing(page: Page, shop: FakeShop, limit: int) -> None:
    shop.category("cat", [[Card("A", "1")]])
    page.goto(f"{BASE}/cat")
    assert collector_for(page, "cat").collect(Decimal("10"), limit) == SearchOutcome([], [])
    assert len(shop.page_requests("/cat")) == 1  # only the initial goto


def test_max_pages_above_the_page_count_stops_at_the_end(page: Page, shop: FakeShop) -> None:
    shop.category("cat", [[Card("A", "1")], [Card("B", "1")]])
    page.goto(f"{BASE}/cat")
    outcome = collector_for(page, "cat").collect(Decimal("10"), limit=10, max_pages=50)
    assert outcome.pages == [1, 2]


@pytest.mark.parametrize("max_pages", [0, -1])
def test_non_positive_max_pages_is_rejected(page: Page, shop: FakeShop, max_pages: int) -> None:
    shop.category("cat", [[Card("A", "1")], [Card("B", "1")]])
    page.goto(f"{BASE}/cat")
    with pytest.raises(ValueError, match="max_pages must be a positive integer"):
        collector_for(page, "cat").collect(Decimal("10"), limit=5, max_pages=max_pages)
    assert len(shop.page_requests("/cat")) == 1  # nothing read beyond the initial goto


def test_reused_collector_carries_no_state(page: Page, shop: FakeShop) -> None:
    shop.category("cat", [[Card("A", "1"), Card("B", "1")], [Card("C", "1")]])
    page.goto(f"{BASE}/cat")
    collector = collector_for(page, "cat")

    first = collector.collect(Decimal("10"), limit=3)
    page.goto(f"{BASE}/cat")
    second = collector.collect(Decimal("10"), limit=3)

    assert titles(first) == titles(second) == ["A", "B", "C"]  # 'seen' URLs are not remembered between calls
    assert first.pages == second.pages == [1, 2]
    assert first.products is not second.products and first.pages is not second.pages
    first.products.clear()
    first.pages.clear()
    assert titles(second) == ["A", "B", "C"] and second.pages == [1, 2]


def test_collectors_on_two_listings_are_independent(page: Page, shop: FakeShop) -> None:
    shop.category("one", [[Card("A", "1")], [Card("B", "1")]])
    shop.category("two", [[Card("A", "1"), Card("Z", "1")]])  # same URL 'A' as on the first listing
    page.goto(f"{BASE}/one")
    first = collector_for(page, "one").collect(Decimal("10"), limit=5)
    page.goto(f"{BASE}/two")
    second = collector_for(page, "two").collect(Decimal("10"), limit=5)
    assert (titles(first), first.pages) == (["A", "B"], [1, 2])
    assert (titles(second), second.pages) == (["A", "Z"], [1])


def test_next_pointing_to_the_current_page_stops(page: Page, shop: FakeShop, caplog) -> None:
    raw_listing(shop, "self", lambda n: grid_html([Card(f"P{n}", "1")]) + pager(n, f"/self?pagenumber={n}"))
    page.goto(f"{BASE}/self")
    with caplog.at_level(logging.WARNING):
        outcome = collector_for(page, "self").collect(Decimal("10"), limit=5)
    assert titles(outcome) == ["P1"] and outcome.pages == [1]
    assert len(shop.page_requests("/self")) == 1
    assert "already read" in caplog.text


def test_next_href_without_page_number_falls_back_to_current_plus_one(page: Page, shop: FakeShop) -> None:
    def body(query: dict[str, list[str]]) -> str:
        number = int(query.get("p", ["1"])[0])
        next_href = f"/odd?p={number + 1}" if number < 3 else None
        return f'<div class="page-body">{grid_html([Card(f"P{number}", "1")])}{pager(number, next_href)}</div>'

    shop.html("/odd", body)
    page.goto(f"{BASE}/odd")
    outcome = collector_for(page, "odd").collect(Decimal("10"), limit=5)
    assert titles(outcome) == ["P1", "P2", "P3"]
    assert outcome.pages == [1, 2, 3]


def test_unreadable_cards_are_skipped_in_order(page: Page, shop: FakeShop) -> None:
    cards = [
        Card("Call", "Call for pricing"),
        Card("First", "1.00"),
        Card("No price element", None),
        Card("Empty price", ""),
        Card("Second", "2.00"),
    ]
    shop.category("mixed", [cards])
    page.goto(f"{BASE}/mixed")
    assert titles(collector_for(page, "mixed").collect(Decimal("10"), limit=5)) == ["First", "Second"]


def test_grid_where_no_card_is_readable(page: Page, shop: FakeShop) -> None:
    shop.category("broken", [[Card("A", "n/a")], [Card("B", None)]])
    page.goto(f"{BASE}/broken")
    assert collector_for(page, "broken").collect(Decimal("10"), limit=5) == SearchOutcome([], [1, 2])


def test_loading_tile_without_title_and_price_is_skipped(page: Page, shop: FakeShop) -> None:
    grid = f'<div class="product-grid">{SKELETON_CARD}{Card("Ready", "1").html()}</div>'
    raw_listing(shop, "loading", lambda _number: grid)
    page.goto(f"{BASE}/loading")
    page.set_default_timeout(1000)
    assert titles(collector_for(page, "loading").collect(Decimal("10"), limit=5)) == ["Ready"]
