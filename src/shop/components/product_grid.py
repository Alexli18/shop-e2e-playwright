"""Product listing extracted with XPath (works for grid and list view modes)."""

import logging

from playwright.sync_api import Locator, Page

from shop import markup
from shop.components.product_card import ProductCard
from shop.models import ProductSummary

log = logging.getLogger(__name__)


def _has_class(name: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


class ProductGrid:
    # Only the listing of the main column: the grid must be a direct child of the search results or of
    # the page body, so sidebar blocks and 'related' / 'also bought' grids on the page cannot leak in.
    _CARDS = (
        f"xpath=//div[{_has_class('center-2')}]"
        f"//div[{_has_class(markup.SEARCH_RESULTS)} or {_has_class('page-body')}]"
        f"/div[{_has_class('product-grid')} or {_has_class('product-list')}]"
        f"//div[{_has_class(markup.PRODUCT_ITEM)} and @data-productid]"
    )

    def __init__(self, page: Page) -> None:
        self._cards = page.locator(self._CARDS)

    @property
    def card_locator(self) -> Locator:
        return self._cards

    def cards(self) -> list[ProductCard]:
        return [ProductCard(self._cards.nth(index)) for index in range(self._cards.count())]

    def summaries(self) -> list[ProductSummary]:
        """Summaries of all cards on the current page; cards without a readable price are skipped."""
        summaries = []
        for card in self.cards():
            try:
                summaries.append(card.summary())
            except ValueError as error:
                log.warning("Skipping product card: %s", error)
        return summaries
