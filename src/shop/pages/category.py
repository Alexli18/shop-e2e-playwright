"""Category listing with its pager (e.g. /apparel-shoes)."""

from playwright.sync_api import Page

from shop.pages.base import ListingPage


class CategoryPage(ListingPage):
    def __init__(self, page: Page, base_url: str, slug: str) -> None:
        super().__init__(page, base_url)
        self.path = f"/{slug.strip('/')}"
