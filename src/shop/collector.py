"""Collecting products under a price across listing pages (search results or a category)."""

from decimal import Decimal
import logging

from shop.components import Pager, ProductGrid
from shop.models import ProductSummary, SearchOutcome

log = logging.getLogger(__name__)


class ProductCollector:
    """Reads a listing through its grid and pager; the page objects stay free of collection rules.

    Rules: price <= max_price, at most `limit` products, no duplicate URLs, follow Next until enough are
    found, the pages end, `max_pages` pages were read, or Next points back to a page already read.
    """

    MAX_PAGES = 20  # guard against a pager that never ends

    def __init__(self, grid: ProductGrid, pager: Pager) -> None:
        self._grid = grid
        self._pager = pager

    def collect(self, max_price: Decimal, limit: int, max_pages: int | None = None) -> SearchOutcome:
        """Products found and the page numbers read (in order); `max_pages` defaults to MAX_PAGES."""
        max_pages = self.MAX_PAGES if max_pages is None else max_pages
        if type(max_pages) is not int or max_pages <= 0:
            raise ValueError(f"max_pages must be a positive integer, got {max_pages!r}")
        found: list[ProductSummary] = []
        seen: set[str] = set()
        pages: list[int] = []
        while len(found) < limit:
            pages.append(self._pager.current_page())
            for product in self._grid.summaries():
                if product.price <= max_price and product.url not in seen:
                    seen.add(product.url)
                    found.append(product)
                    if len(found) == limit:
                        break
            if len(found) >= limit:
                break
            if len(pages) >= max_pages:
                log.warning("Stopped after %d page(s) (max_pages)", max_pages)
                break
            if (target := self._pager.next_page()) in pages:
                log.warning("Next points back to page %s, already read; stopping", target)
                break
            if not self._pager.go_next():
                break
        log.info("Collected %d product(s) priced <= %s from page(s) %s", len(found), max_price, pages)
        return SearchOutcome(found, pages)
