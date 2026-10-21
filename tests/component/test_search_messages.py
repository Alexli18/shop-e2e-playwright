"""SearchPage.result_message: the text the shop shows instead of results (empty result, too short a term)."""

from playwright.sync_api import Page, expect
import pytest

from shop.pages import SearchPage
from tests.component.fakeshop import BASE, FakeShop, fixture, no_results_html, render

pytestmark = pytest.mark.component

SHORT_TERM_WARNING = (  # live markup of /search?q=ab (probed)
    '<div class="search-results"><strong class="warning">Search term minimum length is 3 characters</strong></div>'
)


def serve_search(shop: FakeShop, results_for) -> None:
    def body(query: dict[str, list[str]]) -> str:
        term = (query.get("Q") or query.get("q") or [""])[0]
        results = results_for(term) if term else ""
        return render(fixture("search_form.html"), query=term, results=results, advanced_toggle="", advanced_block="")

    shop.html("/search", body)


def test_no_results_message(page: Page, shop: FakeShop) -> None:
    serve_search(shop, lambda _term: no_results_html())
    results = SearchPage(page, BASE).open().search("zzzzqqq")
    expect(results.result_message).to_have_text("No products were found that matched your criteria.")
    assert results.grid.cards() == []


def test_short_term_warning_is_the_result_message(page: Page, shop: FakeShop) -> None:
    serve_search(shop, lambda _term: SHORT_TERM_WARNING)
    results = SearchPage(page, BASE).open().search("ab")
    assert results.grid.cards() == []
    expect(results.result_message).to_have_text("Search term minimum length is 3 characters", timeout=1000)
