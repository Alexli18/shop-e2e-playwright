"""Base page objects shared by all pages."""

from typing import Self

from playwright.sync_api import Page

from shop.components import Header, Pager, ProductGrid


class BasePage:
    """Shared header and navigation; `path` is None for pages without a fixed URL (product pages)."""

    path: str | None = None

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.header = Header(page)

    @property
    def url(self) -> str:
        if self.path is None:
            raise TypeError(f"{type(self).__name__} has no fixed URL")
        return f"{self.base_url}{self.path}"

    def open(self) -> Self:
        self.page.goto(self.url)
        return self


class ListingPage(BasePage):
    """A page with a product grid and an optional pager (search results, categories).

    Collection rules (price, limit, paging guards) live in shop.collector.ProductCollector."""

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)
        self.grid = ProductGrid(page)
        self.pager = Pager(page)
