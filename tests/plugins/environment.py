"""Profiles, browser settings, timeouts, output directories and failure artifacts, on top of pytest-playwright."""

from collections.abc import Generator, Iterator
import os
from pathlib import Path
import shutil
from typing import Any

import allure
from playwright.sync_api import BrowserContext, expect
import pytest

from shop.config import Credentials, Environment, credentials_from_env, load_environment
from tests.support.markers import OFFLINE_LAYERS
from tests.support.paths import ENVIRONMENTS

# Unit and component tests use local HTML that renders in milliseconds: fail fast instead of waiting.
OFFLINE_TIMEOUT_MS = 3000


def offline(node: pytest.Item) -> bool:
    return any(node.get_closest_marker(layer) for layer in OFFLINE_LAYERS)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--env", default=None, help="Profile from config/environments.json (default: SHOP_ENV, then the file's default)"
    )


def environment_of(config: pytest.Config) -> Environment:
    name = config.getoption("--env") or os.environ.get("SHOP_ENV")
    try:
        return load_environment(ENVIRONMENTS, name)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None


def _parallel(config: pytest.Config) -> bool:
    """True when pytest-xdist runs more than one worker (-n 4, -n auto, ...)."""
    workers = getattr(config.option, "numprocesses", None)
    return workers not in (None, 0, 1, "0", "1")


@pytest.hookimpl(trylast=True)  # after allure-pytest has set up its results directory
def pytest_configure(config: pytest.Config) -> None:
    """Controller-only work (once per run, never on xdist workers): checks, cleaning the output directories,
    and Allure's Environment widget."""
    if hasattr(config, "workerinput"):  # an xdist worker: the controller already did this
        return
    if os.environ.get("SHOP_EMAIL") and _parallel(config):
        raise pytest.UsageError(
            "SHOP_EMAIL/SHOP_PASSWORD share one account (and its cart) between all tests; "
            "run them without -n, or unset them to register a new user per test"
        )
    # pytest-playwright would clean --output in every worker's session (see delete_output_dir below).
    shutil.rmtree(config.getoption("--output"), ignore_errors=True)
    alluredir = config.getoption("allure_report_dir", default=None)
    if not alluredir:
        return
    # Fresh results per run; --clean-alluredir is not used because every xdist worker would apply it.
    shutil.rmtree(alluredir, ignore_errors=True)
    Path(alluredir).mkdir(parents=True)
    environment = environment_of(config)
    lines = {
        "Profile": environment.name,
        "Base.URL": config.getoption("--base-url") or environment.base_url,
        "Browser": ",".join(config.getoption("browser") or ["chromium"]),
        "Headed": config.getoption("headed"),
        "Account": "existing (SHOP_EMAIL)" if os.environ.get("SHOP_EMAIL") else "new user per test",
    }
    text = "".join(f"{key}={value}\n" for key, value in lines.items())
    (Path(alluredir) / "environment.properties").write_text(text, encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def delete_output_dir() -> None:
    """Replaces pytest-playwright's fixture of the same name, which deletes --output at the start of every
    session: with xdist each worker would delete artifacts that other workers already wrote. The controller
    cleans it once in pytest_configure instead."""


@pytest.fixture(scope="session")
def environment(pytestconfig: pytest.Config) -> Environment:
    return environment_of(pytestconfig)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict, environment: Environment) -> dict:
    """The profile's slow_mo unless --slowmo was given on the command line."""
    if environment.slow_mo and not browser_type_launch_args.get("slow_mo"):
        return {**browser_type_launch_args, "slow_mo": environment.slow_mo}
    return browser_type_launch_args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict, environment: Environment) -> dict:
    viewport = {"width": environment.viewport.width, "height": environment.viewport.height}
    return {**browser_context_args, "locale": environment.locale, "viewport": viewport}


@pytest.fixture
def context(
    context: BrowserContext, environment: Environment, request: pytest.FixtureRequest
) -> Iterator[BrowserContext]:
    """pytest-playwright's context with the right timeouts: short for unit/component tests, the profile's otherwise.

    expect()'s timeout is global in Playwright, so it is set here per test and reset to Playwright's default
    afterwards: nothing depends on fixture order or on which test ran before."""
    short = offline(request.node)
    timeout = OFFLINE_TIMEOUT_MS if short else environment.timeout_ms
    context.set_default_timeout(timeout)
    context.set_default_navigation_timeout(timeout)
    expect.set_options(timeout=OFFLINE_TIMEOUT_MS if short else environment.expect_timeout_ms)
    yield context
    expect.set_options(timeout=None)


@pytest.fixture(scope="session")
def shop_credentials() -> Credentials | None:
    """Existing account from SHOP_EMAIL / SHOP_PASSWORD, or None to register a new user per test."""
    try:
        return credentials_from_env()
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> Generator[None, Any, None]:
    """Attach pytest-playwright's failure screenshot and trace to Allure.

    pytest-playwright stores them when the teardown report is made and lists them in user_properties.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "teardown":
        return
    for key, path in report.user_properties:
        file = Path(item.config.invocation_params.dir, str(path))
        if key == "playwright_screenshot" and file.is_file():
            allure.attach.file(str(file), name="failure screenshot", attachment_type=allure.attachment_type.PNG)
        elif key == "playwright_trace" and file.is_file():
            allure.attach.file(str(file), name="trace.zip (open with: playwright show-trace)", extension="zip")
