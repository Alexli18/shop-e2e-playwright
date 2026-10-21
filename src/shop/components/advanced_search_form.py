"""Advanced search form on /search: keyword, 'Advanced search' toggle, price range, search in descriptions."""

from decimal import Decimal
import logging

from playwright.sync_api import Page

log = logging.getLogger(__name__)


class AdvancedSearchForm:
    def __init__(self, page: Page) -> None:
        root = page.locator(".search-input form")
        self._query = root.get_by_label("Search keyword:")
        self._advanced = root.get_by_label("Advanced search")
        self._price_from = root.locator("#Pf")
        self._price_to = root.locator("#Pt")
        self._in_descriptions = root.get_by_label("Search In product descriptions")
        self._submit = root.get_by_role("button", name="Search", exact=True)

    def has_price_filter(self) -> bool:
        return self._advanced.count() > 0

    def search(self, query: str, max_price: Decimal | None = None, in_descriptions: bool = False) -> None:
        """Fill the form and submit it; advanced options are used only when the page offers them."""
        self._query.fill(query)
        if self.has_price_filter() and (max_price is not None or in_descriptions):
            self._advanced.check()
            if max_price is not None:
                self._price_from.fill("")
                self._price_to.fill(f"{max_price:.2f}")
            if in_descriptions:
                if self._in_descriptions.count():
                    self._in_descriptions.check()
                else:
                    log.warning("The search form has no 'Search In product descriptions' option")
        self._submit.click()
