"""Marker rules and what markers imply: e2e-only reruns, short timeouts, Allure labels."""

import pytest

from tests.plugins.environment import offline
from tests.support.markers import LAYERS, SUITES, marker_problems

# Whole-test limits (pytest-timeout): unit/component tests take seconds; others get the ini default.
OFFLINE_TEST_TIMEOUT_S = 60
EPICS = {"unit": "Unit", "component": "Component", "e2e": "End-to-end"}


def _allure_label(label_type: str, value: str) -> pytest.MarkDecorator:
    """What allure.epic()/feature()/severity() apply to a test function (allure-pytest's label mark)."""
    return pytest.mark.allure_label(value, label_type=label_type)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--e2e-reruns",
        type=int,
        default=0,
        help="Rerun failed e2e tests this many times (pytest-rerunfailures); other layers are never rerun",
    )


# Markers this plugin adds to items itself; normally registered by their own plugins.
_ADDED_MARKERS = {
    "allure_label": "Allure label (added from the layer/feature/smoke markers)",
    "flaky": "pytest-rerunfailures reruns (added to e2e tests by --e2e-reruns)",
    "timeout": "pytest-timeout limit (added to unit/component tests)",
}


def pytest_configure(config: pytest.Config) -> None:
    """Make sure every marker the suite uses or adds is registered in this process (controller and every
    xdist worker), whether it comes from pyproject.toml or from a plugin that might be disabled (-p no:...).
    Already registered names are not added twice."""
    registered = {line.split(":", 1)[0].split("(", 1)[0].strip() for line in config.getini("markers")}
    for name in (*LAYERS, *SUITES):
        if name not in registered:
            config.addinivalue_line("markers", f"{name}: see the marker list in pyproject.toml")
    for name, description in _ADDED_MARKERS.items():
        if name not in registered:
            config.addinivalue_line("markers", f"{name}: {description}")


@pytest.hookimpl(tryfirst=True)  # before `-m` deselects
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Enforce the marker rules (tests/support/markers.py), allow reruns only for e2e tests (--e2e-reruns),
    give unit/component tests a short whole-test timeout unless they set their own, and map markers to Allure
    labels: layer -> epic, smoke -> severity critical (Allure's Behaviors tab groups by epic)."""
    problems = marker_problems((item.nodeid, {mark.name for mark in item.iter_markers()}) for item in items)
    if problems:
        raise pytest.UsageError("Marker rules violated:\n  " + "\n  ".join(problems))
    e2e_reruns = config.getoption("--e2e-reruns")
    for item in items:
        names = {mark.name for mark in item.iter_markers()}
        if e2e_reruns and "e2e" in names:
            item.add_marker(pytest.mark.flaky(reruns=e2e_reruns))
        if offline(item) and "timeout" not in names:
            item.add_marker(pytest.mark.timeout(OFFLINE_TEST_TIMEOUT_S))
        for layer in names & set(LAYERS):
            item.add_marker(_allure_label("epic", EPICS[layer]))
        if "smoke" in names:
            item.add_marker(_allure_label("severity", "critical"))
