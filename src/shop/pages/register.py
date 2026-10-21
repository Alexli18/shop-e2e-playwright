"""Registration page."""

from playwright.sync_api import Locator, expect

from shop.config import Credentials
from shop.pages.base import BasePage


class RegisterPage(BasePage):
    path = "/register"

    @property
    def _form(self) -> Locator:
        return self.page.locator("form").filter(has=self.page.get_by_role("button", name="Register", exact=True))

    @property
    def result(self) -> Locator:
        return self.page.locator(".page-body .result")

    def submit(
        self, first_name: str, last_name: str, credentials: Credentials, confirm_password: str | None = None
    ) -> None:
        """Fill and submit the form without expecting an outcome (see register for the successful path)."""
        form = self._form
        form.get_by_label("Male", exact=True).check()
        form.get_by_label("First name:").fill(first_name)
        form.get_by_label("Last name:").fill(last_name)
        form.get_by_label("Email:").fill(credentials.email)
        form.get_by_label("Password:", exact=True).fill(credentials.password)
        form.get_by_label("Confirm password:", exact=True).fill(
            credentials.password if confirm_password is None else confirm_password
        )
        form.get_by_role("button", name="Register", exact=True).click()

    def register(self, first_name: str, last_name: str, credentials: Credentials) -> None:
        """Register a new customer; the shop logs the new user in automatically."""
        self.submit(first_name, last_name, credentials)
        expect(self.result).to_contain_text("Your registration completed")
        self.page.get_by_role("button", name="Continue").click()
        self.header.expect_logged_in_as(credentials.email)
