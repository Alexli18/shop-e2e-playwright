"""The project's pytest setup, split by concern into tests/plugins (on top of pytest-playwright).

It lives at the repository root so the plugins' options (`--cases PATH`, `--env NAME`) are registered before
pytest parses the command line, whichever test paths are given.

- environment: profiles (--env), browser settings, timeouts, output directories, failure artifacts
- markers: marker rules, e2e reruns / timeouts / Allure labels derived from markers
- cases: the e2e data cases (--cases)

Helpers for test modules live in tests/support; nothing is imported from conftest files."""

import pytest

from shop.config import Environment

pytest_plugins = [
    "tests.plugins.environment",
    "tests.plugins.markers",
    "tests.plugins.cases",
]


# Kept here, not in a plugin: pytest-playwright registers its own `base_url` fixture during pytest_configure,
# after these plugins, so only a conftest-level definition reliably overrides it.
@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config, environment: Environment) -> str:
    """pytest-playwright's base_url: an explicit --base-url wins over the profile."""
    return (pytestconfig.getoption("--base-url") or environment.base_url).rstrip("/")
