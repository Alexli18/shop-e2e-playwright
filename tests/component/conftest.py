"""Offline fixtures: a routed fake of the demo shop on top of pytest-playwright's context/page.

The short timeouts are applied by tests/plugins/environment.py's `context` for every test marked `component`."""

from collections.abc import Iterator
from pathlib import Path

from playwright.sync_api import BrowserContext
import pytest

from tests.component.fakeshop import FakeShop
from shop.artifacts import RunArtifacts


@pytest.fixture
def shop(context: BrowserContext) -> Iterator[FakeShop]:
    fake = FakeShop(context)
    yield fake
    assert not fake.blocked, f"offline test tried to reach the network: {fake.blocked}"


@pytest.fixture
def artifacts(tmp_path: Path) -> RunArtifacts:
    return RunArtifacts(tmp_path / "run")
