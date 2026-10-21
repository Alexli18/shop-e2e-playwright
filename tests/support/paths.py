"""Repository paths used by the plugins."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENTS = ROOT / "config/environments.json"
DEFAULT_CASES = ROOT / "data/shopping_cases.json"
