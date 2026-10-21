"""One product tile in a listing (search results or category)."""

from decimal import Decimal
from urllib.parse import urljoin

from playwright.sync_api import Locator

from shop import markup
from shop.models import ProductSummary
from shop.prices import parse_price


class ProductCard:
    _TITLE_LINK = f"xpath=.//h2[contains(@class, '{markup.PRODUCT_TITLE}')]/a"
    # 'actual-price' is the price to pay; a discounted card also shows an 'old-price'.
    _PRICE = (
        "xpath=.//div[contains(@class, 'prices')]"
        f"/span[contains(concat(' ', normalize-space(@class), ' '), ' {markup.ACTUAL_PRICE} ')]"
    )

    def __init__(self, root: Locator) -> None:
        self._root = root

    def title(self) -> str:
        """Title text; ValueError when the tile has no title link (e.g. still loading), without waiting."""
        link = self._root.locator(self._TITLE_LINK)
        if link.count() == 0:
            raise ValueError("No title link on the card (still loading?)")
        return link.first.inner_text().strip()

    def url(self) -> str:
        href = self._root.locator(self._TITLE_LINK).first.get_attribute("href") or ""
        return urljoin(self._root.page.url, href)

    def price(self) -> Decimal:
        """Displayed price; ValueError when the card shows none (no waiting for a missing element)."""
        price = self._root.locator(self._PRICE)
        if price.count() == 0:
            raise ValueError("No price element on the card")
        return parse_price(price.first.inner_text())

    def summary(self) -> ProductSummary:
        """Title, absolute URL and price; ValueError (raised fast, never after a timeout) for an unreadable card."""
        title = self.title()
        try:
            return ProductSummary(title, self.url(), self.price())
        except ValueError as error:
            raise ValueError(f"{error}: {title!r}") from None
