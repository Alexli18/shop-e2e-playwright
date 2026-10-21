"""Bar notification shown after AJAX actions such as Add to cart."""

from dataclasses import dataclass

from playwright.sync_api import Page, expect


@dataclass(frozen=True)
class Notice:
    success: bool
    text: str


class Notification:
    def __init__(self, page: Page) -> None:
        self._bar = page.locator("#bar-notification")
        self._outcome = page.locator("#bar-notification.success, #bar-notification.error")

    def dismiss(self) -> None:
        """Close a bar that is still shown (it stays for a few seconds), so the next outcome is not read stale."""
        if self._bar.is_visible():
            self._bar.get_by_title("Close").click()
            expect(self._bar).to_be_hidden()

    def wait_for_outcome(self) -> Notice:
        """Wait until the bar shows a success or an error and read it.

        The shop renders one <p class="content"> per message (a gift card can answer with four
        errors), so all messages are joined with a space.
        """
        expect(self._outcome).to_be_visible()
        expect(self._outcome).to_have_css("opacity", "1")  # fade-in finished: readable in screenshots
        classes = (self._outcome.get_attribute("class") or "").split()
        messages = [" ".join(text.split()) for text in self._bar.locator(".content").all_inner_texts()]
        return Notice("success" in classes, " ".join(message for message in messages if message))
