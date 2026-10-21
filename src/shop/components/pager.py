"""Listing pager: '1 | 2 | Next'."""

import re

from playwright.sync_api import Page, expect

from shop import markup

_PAGE_NUMBER = re.compile(r"[?&]pagenumber=(\d+)", re.IGNORECASE)


class Pager:
    def __init__(self, page: Page) -> None:
        root = page.locator(".pager").first
        self._current = root.locator(f"li.{markup.CURRENT_PAGE}")
        self._next = root.get_by_role("link", name="Next", exact=True)

    def has_next(self) -> bool:
        return self._next.count() > 0

    def current_page(self) -> int:
        return int(self._current.inner_text()) if self._current.count() else 1

    def next_page(self) -> int | None:
        """Page number the Next link points to (from its href, else current + 1); None without Next."""
        if not self.has_next():
            return None
        match = _PAGE_NUMBER.search(self._next.get_attribute("href") or "")
        return int(match.group(1)) if match else self.current_page() + 1

    def go_next(self) -> bool:
        """Open the next page; False when there is no next page."""
        number = self.next_page()
        if number is None:
            return False
        self._next.click()
        expect(self._current).to_have_text(str(number))
        return True
