"""The marker rules enforced at collection time (tests/support/markers.py, applied by tests/plugins/markers.py)."""

import pytest

from tests.support.markers import marker_problems

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "names", [{"unit"}, {"component"}, {"e2e"}, {"e2e", "smoke"}], ids=["unit", "component", "e2e", "e2e-smoke"]
)
def test_valid_marker_sets(names: set[str]) -> None:
    assert marker_problems([("t", names)]) == []


@pytest.mark.parametrize("names", [set(), {"smoke"}, {"unit", "e2e"}], ids=["no-marker", "suite-only", "two-layers"])
def test_violations_are_reported(names: set[str]) -> None:
    [message] = marker_problems([("tests/x.py::test_x", names)])
    assert message.startswith("tests/x.py::test_x: ") and "exactly one layer" in message
