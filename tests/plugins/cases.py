"""Data cases of the e2e scenario (--cases / SHOP_CASES), parametrized at collection time."""

import os
from pathlib import Path

import pytest

from shop.models import ShoppingCase, load_cases
from tests.support.paths import DEFAULT_CASES


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--cases",
        default=None,
        help="Shopping cases JSON for the e2e test (default: SHOP_CASES, then data/shopping_cases.json)",
    )


def _cases_path(config: pytest.Config) -> Path:
    return Path(config.getoption("--cases") or os.environ.get("SHOP_CASES") or DEFAULT_CASES)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize `shopping_case` from the data file at collection time, without importing it at module level.

    A broken file does not break collection: it becomes one e2e test that fails in setup with the loader's
    message, so `pytest -m "unit or component"` still runs. Cases with "smoke": true also get the smoke marker."""
    if "shopping_case" not in metafunc.fixturenames:
        return
    path = _cases_path(metafunc.config)
    try:
        params = [
            pytest.param(case, id=case.name, marks=[pytest.mark.smoke] if case.smoke else [])
            for case in load_cases(path)
        ]
    except (OSError, ValueError) as error:
        params = [pytest.param(error, id="invalid-cases-file", marks=[pytest.mark.smoke])]
    metafunc.parametrize("shopping_case", params, indirect=True)


@pytest.fixture
def shopping_case(request: pytest.FixtureRequest) -> ShoppingCase:
    """The current data case (parametrized by pytest_generate_tests)."""
    if isinstance(request.param, Exception):
        path = _cases_path(request.config)
        pytest.fail(f"Cannot load shopping cases from {path}: {request.param}", pytrace=False)
    return request.param
