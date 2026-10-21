# ReadMeAIBugs — review of the AI-generated test

Static review (no tools), as requested. The original code:

```python
from playwright.sync_api import sync_playwright
from selenium import webdriver
import time

def test_search_functionality():
    browser = sync_playwright().start().chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")
    time.sleep(2)
    search_box = page.locator("#search")
    search_box.fill("playwright testing")
    page.locator(".button").click()
    time.sleep(3)
    results = page.locator(".result-item")
    browser.close()
```

## Problems found

### 1. Unused Selenium import

**What:** `from selenium import webdriver`.
**Why:** Selenium is a different framework and is never used here. Playwright does not use
WebDriver at all — it drives the browser directly. The line only adds a dependency and fails
with `ModuleNotFoundError` where Selenium is not installed.
**Fix:** remove it.

### 2. Hard-coded `time.sleep`

**What:** `time.sleep(2)` and `time.sleep(3)`.
**Why:** a fixed pause is either too short (flaky) or too long (slow) — a response can take
2 seconds or 20. In Playwright it is also unnecessary: `fill()`/`click()` auto-wait for the
element, and `expect()` retries until the condition holds. Results that load via AJAX after
the page "loads" need a wait on that result, not on time.
**Fix:** delete both sleeps; wait for the outcome: `expect(results.first).to_be_visible()`.

### 3. Browser lifecycle inside the test

**What:** `sync_playwright().start()...launch()` and `browser.close()` in the test body.
**Why:** if anything fails mid-test (e.g. on `fill`), `browser.close()` never runs and the
browser stays open. `start()` is never paired with `stop()`, so the Playwright driver process
leaks even when the test passes.
**Fix:** use the pytest-playwright `page` fixture. A fixture prepares the resource and cleans
it up after `yield` even when the test fails; the browser lives per session, a fresh context
and page per test (isolation).

### 4. Fragile and ambiguous locators

**What:** `.button` and `#search`.
**Why:** `.button` is a generic class — if it matches more than one element, Playwright's
strict mode fails the click. `#search` is tied to an implementation id. Both break on a
redesign, while the user still sees a "Search" box and button.
**Fix:** user-facing locators: `get_by_label("Search")`, `get_by_role("button", name="Search")`. (A role locator
for the field depends on its type: `<input type="search">` is a `searchbox`, a plain text input a `textbox`.)
If an element has no role/label, ask developers for a `data-testid`; otherwise a CSS/XPath
scoped to a stable container — kept inside a Page Object.

### 5. No assertion — the test verifies nothing

**What:** `results` is created and never used.
**Why:** there is no `assert`/`expect`, so the test cannot detect a broken search. Even a
presence check is not enough: if search ignored the query and showed the whole catalogue,
"something is visible" would still pass.
**Fix:** assert relevance (results contain the query term), a known expected item, and a
negative case (nonsense query shows "no results").

### 6. Hard-coded URL that cannot work

**What:** `page.goto("https://example.com")`.
**Why:** example.com has no `#search` field, so the test actually fails with a timeout on
`fill` — this is why it "doesn't work as expected". The URL also belongs to configuration,
not to the test.
**Fix:** `base_url` from config/env (`pytest --base-url ...`), and `page.goto("/")`.

### 7. No Page Object, data hard-coded

**What:** locators, actions and the search term all live in the test.
**Why:** every test touching search would repeat the locators; one UI change means editing
every test. The test also reads as clicks, not as a scenario, and new cases need code changes.
**Fix:** a `SearchPage` (locators + actions, no asserts) and test data in an external JSON
file fed to `@pytest.mark.parametrize`.

## Corrected version

```python
# data/search_cases.json
# [{"name": "known-term", "query": "playwright testing", "expect": "playwright"},
#  {"name": "no-results", "query": "zzzzqq", "expect": null}]

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

CASES = json.loads(Path("data/search_cases.json").read_text())


class SearchPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.query = page.get_by_label("Search")
        self.submit = page.get_by_role("button", name="Search")
        self.results = page.locator(".result-item")
        self.no_results = page.get_by_text("No results")

    def open(self) -> None:
        self.page.goto("/")  # base_url comes from configuration

    def search(self, text: str) -> None:
        self.query.fill(text)
        self.submit.click()


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_search(page: Page, case: dict) -> None:
    search = SearchPage(page)
    search.open()
    search.search(case["query"])
    if case["expect"] is None:
        expect(search.no_results).to_be_visible()
    else:
        expect(search.results.first).to_contain_text(case["expect"], ignore_case=True)
```
