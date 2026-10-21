"""Environment profiles and optional credentials."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class Viewport:
    width: int
    height: int


@dataclass(frozen=True)
class Environment:
    """One profile of config/environments.json; everything but base_url has a default."""

    name: str
    base_url: str
    timeout_ms: int = 30_000  # actions and navigation
    expect_timeout_ms: int = 5_000  # web-first assertions (expect)
    locale: str = "en-US"
    viewport: Viewport = Viewport(1366, 900)
    slow_mo: int = 0  # ms between browser operations, for watching a headed run


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str = field(repr=False)  # never printed in logs or tracebacks


_PROFILE_KEYS = {"base_url", "timeout_ms", "expect_timeout_ms", "locale", "viewport", "slow_mo"}


def load_environment(path: Path, name: str | None = None) -> Environment:
    data = json.loads(path.read_text(encoding="utf-8"))
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"{path.name}: expected an object with a non-empty 'profiles' object")
    name = name or data.get("default")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{path.name}: no environment selected and no 'default' profile name")
    if name not in profiles:
        raise ValueError(f"Unknown environment {name!r}; available: {sorted(profiles)}")
    profile = profiles[name]
    if not isinstance(profile, dict):
        raise ValueError(f"Environment {name!r}: the profile must be an object")
    if unknown := set(profile) - _PROFILE_KEYS:
        raise ValueError(f"Environment {name!r}: unknown key(s) {sorted(unknown)}")
    base_url = str(profile.get("base_url", ""))
    if not base_url.startswith(("http://", "https://")):
        raise ValueError(f"Environment {name!r}: base_url must be an http(s) URL")
    defaults = Environment(name, base_url)
    viewport = profile.get("viewport", {"width": defaults.viewport.width, "height": defaults.viewport.height})
    if not isinstance(viewport, dict):
        raise ValueError(f"Environment {name!r}: viewport must be an object with width and height")
    locale = profile.get("locale", defaults.locale)
    if not isinstance(locale, str) or not locale.strip():
        raise ValueError(f"Environment {name!r}: locale must be a non-empty string")
    return Environment(
        name,
        base_url.rstrip("/"),
        timeout_ms=_positive_int(name, "timeout_ms", profile.get("timeout_ms", defaults.timeout_ms)),
        expect_timeout_ms=_positive_int(
            name, "expect_timeout_ms", profile.get("expect_timeout_ms", defaults.expect_timeout_ms)
        ),
        locale=locale,
        viewport=Viewport(
            _positive_int(name, "viewport.width", viewport.get("width")),
            _positive_int(name, "viewport.height", viewport.get("height")),
        ),
        slow_mo=_positive_int(name, "slow_mo", profile.get("slow_mo", 0), allow_zero=True),
    )


def _positive_int(profile: str, key: str, value: object, allow_zero: bool = False) -> int:
    if type(value) is not int or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"Environment {profile!r}: {key} must be a positive integer, got {value!r}")
    return value


def credentials_from_env(environ: Mapping[str, str] = os.environ) -> Credentials | None:
    """Existing-account credentials (SHOP_EMAIL / SHOP_PASSWORD); None means register a new user."""
    email, password = environ.get("SHOP_EMAIL"), environ.get("SHOP_PASSWORD")
    if email and password:
        return Credentials(email, password)
    if email or password:
        raise ValueError("Set both SHOP_EMAIL and SHOP_PASSWORD, or neither")
    return None
