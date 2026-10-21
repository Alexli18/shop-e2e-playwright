"""Cart totals block: Sub-Total, Shipping, Tax, Total."""

from decimal import Decimal

from playwright.sync_api import Page

from shop import markup
from shop.prices import parse_price


class CartTotals:
    def __init__(self, page: Page) -> None:
        self._root = page.locator(f"table.{markup.CART_TOTALS}")

    def sub_total(self) -> Decimal:
        return self._value("Sub-Total:")

    def total(self) -> Decimal:
        return self._value("Total:")

    def _value(self, caption: str) -> Decimal:
        # Exact caption match, so 'Total:' does not also match 'Sub-Total:'.
        cell = self._root.locator(
            f"xpath=.//tr[td[contains(@class, 'cart-total-left')][normalize-space()='{caption}']]"
            "/td[contains(@class, 'cart-total-right')]"
        )
        return parse_price(cell.inner_text())
