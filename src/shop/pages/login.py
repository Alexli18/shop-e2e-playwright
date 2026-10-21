"""Login page."""

from playwright.sync_api import Locator

from shop.config import Credentials
from shop.pages.base import BasePage


class LoginPage(BasePage):
    path = "/login"

    @property
    def _form(self) -> Locator:
        return self.page.locator("form").filter(has=self.page.get_by_role("button", name="Log in", exact=True))

    def submit(self, credentials: Credentials) -> None:
        """Fill and submit the form without expecting an outcome (see log_in for the successful path)."""
        self._form.get_by_label("Email:").fill(credentials.email)
        self._form.get_by_label("Password:").fill(credentials.password)
        self._form.get_by_role("button", name="Log in").click()

    def log_in(self, credentials: Credentials) -> None:
        """Log in and verify that the header shows the account email."""
        self.submit(credentials)
        self.header.expect_logged_in_as(credentials.email)
