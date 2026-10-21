"""Shopping cart page."""

from decimal import Decimal
from typing import Self

from playwright.sync_api import Locator, Page, expect

from shop.components import CartTable, CartTotals
from shop.models import CartSnapshot
from shop.pages.base import BasePage


class CartPage(BasePage):
    path = "/cart"

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)
        self.table = CartTable(page)
        self.totals = CartTotals(page)
        self._content = page.locator(".order-summary-content")

    def open(self) -> Self:
        super().open()
        expect(self._content).to_be_visible()
        return self

    def is_empty(self) -> bool:
        return self.table.count() == 0

    def sub_total(self) -> Decimal:
        """Sub-Total exactly as the shop shows it; an empty cart has no totals block and counts as 0."""
        return Decimal("0") if self.is_empty() else self.totals.sub_total()

    def snapshot(self) -> CartSnapshot:
        return CartSnapshot(self.table.entries(), self.sub_total())

    @property
    def _update_button(self) -> Locator:
        return self._content.get_by_role("button", name="Update shopping cart")

    def clear(self) -> None:
        """Remove every row (used when an existing account starts with a non-empty cart)."""
        if self.is_empty():
            return
        for checkbox in self.table.remove_checkboxes().all():
            checkbox.check()
        self._update_button.click()
        expect(self._content).to_contain_text("Your Shopping Cart is empty!")
