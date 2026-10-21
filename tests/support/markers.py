"""The marker taxonomy: exactly one layer per test, plus the smoke suite for CI selection."""

from collections.abc import Iterable

LAYERS = ("unit", "component", "e2e")
OFFLINE_LAYERS = ("unit", "component")  # no network, short timeouts
SUITES = ("smoke",)


def marker_problems(items: Iterable[tuple[str, set[str]]]) -> list[str]:
    """Rule violations for (test id, marker names) pairs: every test needs exactly one layer marker."""
    problems = []
    for nodeid, names in items:
        layers = sorted(names & set(LAYERS))
        if len(layers) != 1:
            problems.append(f"{nodeid}: needs exactly one layer marker of {LAYERS}, has {layers}")
    return problems
