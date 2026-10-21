"""The `context` fixture (tests/plugins/environment.py) gives component tests short timeouts, so a broken
locator fails in about 3 s instead of the profile's 15 s / 10 s. Effective values are read through Playwright internals
(`_timeout_settings`, `expect._timeout`): there is no public getter."""

import time

from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import pytest

from tests.component.fakeshop import BASE, FakeShop

pytestmark = pytest.mark.component

OFFLINE_MS = 3000


def effective(page: Page) -> tuple[float, float, float | None]:
    settings = page._impl_obj._timeout_settings  # noqa: SLF001 - no public getter
    return settings.timeout(), settings.navigation_timeout(), expect._timeout  # noqa: SLF001


def test_offline_test_gets_the_short_timeouts(page: Page) -> None:
    assert effective(page) == (OFFLINE_MS, OFFLINE_MS, OFFLINE_MS)


def test_offline_failures_fail_in_about_three_seconds(page: Page, shop: FakeShop) -> None:
    shop.html("/blank", "<p>nothing here</p>")
    page.goto(f"{BASE}/blank")

    started = time.monotonic()
    with pytest.raises(AssertionError):
        expect(page.locator("#missing")).to_be_visible()
    expect_elapsed = time.monotonic() - started

    started = time.monotonic()
    with pytest.raises(PlaywrightTimeoutError):
        page.locator("#missing").click()
    action_elapsed = time.monotonic() - started

    assert 2.5 <= expect_elapsed < 6, expect_elapsed
    assert 2.5 <= action_elapsed < 6, action_elapsed
