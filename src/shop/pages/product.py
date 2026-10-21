"""Product details page."""

from decimal import Decimal
from typing import Self

from playwright.sync_api import Locator, expect

from shop.components import Notice, Notification, ProductOptions
from shop.pages.base import BasePage
from shop.prices import parse_price


class ProductPage(BasePage):
    """A product details page; it has no fixed URL, so it is opened with open_url()."""

    def open_url(self, url: str) -> Self:
        self.page.goto(url)
        expect(self.title_heading).to_be_visible()
        return self

    @property
    def _essential(self) -> Locator:
        # The main product block; related-product tiles below have their own buttons.
        return self.page.locator(".product-essential")

    @property
    def title_heading(self) -> Locator:
        return self._essential.get_by_role("heading", level=1)

    @property
    def add_to_cart_button(self) -> Locator:
        return self._essential.get_by_role("button", name="Add to cart", exact=True)

    @property
    def options(self) -> ProductOptions:
        return ProductOptions(self._essential)

    def title(self) -> str:
        return self.title_heading.inner_text().strip()

    def price(self) -> Decimal | None:
        """Price shown on the page (before option surcharges); None when the page shows no price."""
        price = self._essential.locator(".product-price")
        return parse_price(price.first.inner_text()) if price.count() else None

    def availability(self) -> str:
        """Stock text such as 'In stock' / 'Out of stock'; empty when the product shows none."""
        stock = self._essential.locator(".stock .value")
        return stock.inner_text().strip() if stock.count() else ""

    @property
    def _purchase(self) -> Locator:
        # Qty, Add to cart and Add to wishlist; the shop leaves the block empty for a product it does not sell.
        return self._essential.locator(".add-to-cart")

    def unavailable_reason(self) -> str | None:
        """Why the product cannot be bought right now, or None when it can.

        Only the shop's own signs count: 'Out of stock', an empty purchase block, or a block that offers only Add
        to wishlist. Any other page must show Add to cart, or this fails: a renamed button or a changed theme must
        not turn every product into 'unavailable' and let the cart check pass on an empty cart."""
        if self.availability().lower() == "out of stock":
            return "Out of stock"
        expect(self._purchase, "no purchase block on the product page: has the markup changed?").to_be_attached()
        if self._purchase.locator("input, button, select").count() == 0:
            return "Not sold online (empty purchase block)"
        wishlist = self._purchase.get_by_role("button", name="Add to wishlist", exact=True).count()
        if wishlist and self._purchase.get_by_role("button").count() == wishlist:
            return "Wishlist only (no Add to cart)"
        expect(
            self.add_to_cart_button, "the purchase block has no 'Add to cart' button: has the markup changed?"
        ).to_be_visible()
        return None

    def set_quantity(self, quantity: int) -> None:
        field = self._essential.get_by_label("Qty:")
        field.fill(str(quantity))
        expect(field).to_have_value(str(quantity))

    def add_to_cart(self) -> Notice:
        """Click Add to cart and return the success or error notification (a previous bar is closed first)."""
        notification = Notification(self.page)
        notification.dismiss()
        self.add_to_cart_button.click()
        notice = notification.wait_for_outcome()
        expect(self.page.locator(".ajax-loading-block-window")).to_be_hidden()
        return notice
