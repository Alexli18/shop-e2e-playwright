"""What every workflow shares: the page it drives, the shop's base URL, and its run artifacts."""

from pathlib import Path

from playwright.sync_api import Page

from shop.artifacts import RunArtifacts


class BaseWorkflow:
    def __init__(self, page: Page, base_url: str, artifacts: RunArtifacts) -> None:
        self.page = page
        self.base_url = base_url
        self.artifacts = artifacts

    def _screenshot(self, name: str, page: Page | None = None) -> Path:
        """A numbered screenshot of `page` (default: the workflow's page) in the run artifacts and Allure."""
        return self.artifacts.screenshot(page or self.page, name)
