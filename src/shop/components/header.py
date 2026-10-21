"""Header shown on every page: account link, cart counter, log in / log out."""

import re

from playwright.sync_api import Locator, Page, expect

from shop import markup


class Header:
    def __init__(self, page: Page) -> None:
        self._links = page.locator(f".header .{markup.HEADER_LINKS}")

    @property
    def account(self) -> Locator:
        return self._links.locator(f"a.{markup.ACCOUNT_LINK}")

    @property
    def log_out_link(self) -> Locator:
        return self._links.get_by_role("link", name="Log out", exact=True)

    @property
    def log_in_link(self) -> Locator:
        return self._links.get_by_role("link", name="Log in", exact=True)

    @property
    def cart_counter(self) -> Locator:
        return self._links.locator(f".{markup.CART_COUNTER}")

    def expect_logged_in_as(self, email: str) -> None:
        expect(self.account).to_have_text(email)
        expect(self.log_out_link).to_be_visible()

    def log_out(self) -> None:
        self.log_out_link.click()
        expect(self.log_in_link).to_be_visible()

    def cart_quantity(self) -> int:
        """Counter text such as '(3)' -> 3."""
        match = re.search(r"\d+", self.cart_counter.inner_text())
        return int(match.group()) if match else 0
