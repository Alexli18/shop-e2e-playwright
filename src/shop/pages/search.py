"""Advanced search page."""

from decimal import Decimal
import re
from typing import Self

from playwright.sync_api import Locator, Page, expect

from shop import markup
from shop.components import AdvancedSearchForm
from shop.pages.base import ListingPage


class SearchPage(ListingPage):
    path = "/search"

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)
        self.form = AdvancedSearchForm(page)

    def search(self, query: str, max_price: Decimal | None = None, in_descriptions: bool = False) -> Self:
        """Submit a search; results (or the 'no products' message) are rendered server side, 8 per page."""
        self.form.search(query, max_price, in_descriptions)
        expect(self.page).to_have_url(re.compile(r"/search\?.*\bq=", re.IGNORECASE))
        expect(self.page.locator(f".{markup.SEARCH_RESULTS}")).to_be_visible()
        # Zero cards is a valid result only next to the shop's message; neither means the markup changed.
        expect(
            self.grid.card_locator.or_(self.result_message).first,
            "search shows neither product cards nor a result message: has the markup changed?",
        ).to_be_attached()
        return self

    @property
    def result_message(self) -> Locator:
        """The message shown instead of results: 'No products were found that matched your criteria.', or the
        warning 'Search term minimum length is 3 characters'."""
        classes = ", ".join(f".{markup.SEARCH_RESULTS} strong.{name}" for name in markup.RESULT_MESSAGES)
        return self.page.locator(classes)
