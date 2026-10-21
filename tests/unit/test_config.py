"""config.load_environment / credentials_from_env."""

import json
from pathlib import Path

import pytest

from shop.config import Credentials, Environment, Viewport, credentials_from_env, load_environment

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def environments(tmp_path: Path) -> Path:
    path = tmp_path / "environments.json"
    path.write_text(
        json.dumps(
            {
                "default": "prod",
                "profiles": {
                    "prod": {"base_url": "https://demowebshop.tricentis.com/"},
                    "local": {"base_url": "http://localhost:8080"},
                    "broken": {"base_url": "demowebshop.tricentis.com"},
                    "ftp": {"base_url": "ftp://demowebshop.tricentis.com"},
                    "empty": {"base_url": ""},
                    "missing": {},
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_default_profile(environments: Path) -> None:
    assert load_environment(environments) == Environment("prod", "https://demowebshop.tricentis.com")


def test_named_profile(environments: Path) -> None:
    assert load_environment(environments, "local") == Environment("local", "http://localhost:8080")


def test_project_config_default_profile() -> None:
    environment = load_environment(ROOT / "config/environments.json")
    assert environment.base_url == "https://demowebshop.tricentis.com"


def test_unknown_profile_lists_available(environments: Path) -> None:
    with pytest.raises(ValueError, match=r"Unknown environment 'staging'.*'local'.*'prod'"):
        load_environment(environments, "staging")


@pytest.mark.parametrize("name", ["broken", "ftp", "empty", "missing"])
def test_invalid_url_rejected(environments: Path, name: str) -> None:
    with pytest.raises(ValueError, match="http"):
        load_environment(environments, name)


def test_both_credentials() -> None:
    credentials = credentials_from_env({"SHOP_EMAIL": "qa@example.com", "SHOP_PASSWORD": "s3cr3t!"})
    assert credentials == Credentials("qa@example.com", "s3cr3t!")


@pytest.mark.parametrize("environ", [{}, {"SHOP_EMAIL": "", "SHOP_PASSWORD": ""}, {"OTHER": "x"}])
def test_no_credentials_means_register(environ: dict) -> None:
    assert credentials_from_env(environ) is None


@pytest.mark.parametrize(
    "environ",
    [
        {"SHOP_EMAIL": "qa@example.com"},
        {"SHOP_PASSWORD": "s3cr3t!"},
        {"SHOP_EMAIL": "qa@example.com", "SHOP_PASSWORD": ""},
        {"SHOP_EMAIL": "", "SHOP_PASSWORD": "s3cr3t!"},
    ],
)
def test_only_one_credential_rejected(environ: dict) -> None:
    with pytest.raises(ValueError, match="both"):
        credentials_from_env(environ)


def test_password_not_in_repr() -> None:
    credentials = Credentials("qa@example.com", "s3cr3t-Pa55")
    assert "qa@example.com" in repr(credentials)
    assert "s3cr3t-Pa55" not in repr(credentials)
    assert "s3cr3t-Pa55" not in str(credentials)
    assert "s3cr3t-Pa55" not in f"{[credentials]}"


# ------------------------------------------------------------- profile options (timeouts, locale, viewport, slow_mo)


def write_profile(tmp_path: Path, **profile: object) -> Path:
    path = tmp_path / "env.json"
    path.write_text(
        json.dumps({"default": "p", "profiles": {"p": {"base_url": "https://shop.test", **profile}}}), encoding="utf-8"
    )
    return path


def test_profile_option_defaults(tmp_path: Path) -> None:
    assert load_environment(write_profile(tmp_path)) == Environment(
        "p",
        "https://shop.test",
        timeout_ms=30_000,
        expect_timeout_ms=5_000,
        locale="en-US",
        viewport=Viewport(1366, 900),
        slow_mo=0,
    )


def test_profile_options_loaded(tmp_path: Path) -> None:
    environment = load_environment(
        write_profile(
            tmp_path,
            timeout_ms=45000,
            expect_timeout_ms=20000,
            locale="he-IL",
            viewport={"width": 1920, "height": 1080},
            slow_mo=250,
        )
    )
    assert (environment.timeout_ms, environment.expect_timeout_ms, environment.locale) == (45000, 20000, "he-IL")
    assert environment.viewport == Viewport(1920, 1080)
    assert environment.slow_mo == 250


@pytest.mark.parametrize("name", ["demo-webshop", "ci", "debug"])
def test_project_profiles_are_valid(name: str) -> None:
    environment = load_environment(ROOT / "config/environments.json", name)
    assert environment.timeout_ms > 0 and environment.expect_timeout_ms > 0


@pytest.mark.parametrize("key", ["timeout_ms", "expect_timeout_ms"])
@pytest.mark.parametrize("value", [0, -1, "1000", 1500.0, True, None, [1000]])
def test_bad_timeouts_rejected(tmp_path: Path, key: str, value: object) -> None:
    with pytest.raises(ValueError, match=f"{key} must be a positive integer"):
        load_environment(write_profile(tmp_path, **{key: value}))


@pytest.mark.parametrize("value", [-1, "250", 2.5, None, False])
def test_bad_slow_mo_rejected(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError, match="slow_mo"):
        load_environment(write_profile(tmp_path, slow_mo=value))


def test_slow_mo_zero_is_allowed(tmp_path: Path) -> None:
    assert load_environment(write_profile(tmp_path, slow_mo=0)).slow_mo == 0


@pytest.mark.parametrize("value", ["", 5, None, ["en-US"]])
def test_bad_locale_rejected(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError, match="locale"):
        load_environment(write_profile(tmp_path, locale=value))


@pytest.mark.parametrize(
    ("viewport", "message"),
    [
        ([1366, 900], "viewport must be an object"),
        ("1366x900", "viewport must be an object"),
        ({}, "viewport.width"),
        ({"width": 800}, "viewport.height"),
        ({"width": 0, "height": 600}, "viewport.width"),
        ({"width": 800, "height": -1}, "viewport.height"),
        ({"width": "800", "height": 600}, "viewport.width"),
        ({"width": 800.0, "height": 600}, "viewport.width"),
    ],
)
def test_bad_viewport_rejected(tmp_path: Path, viewport: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_environment(write_profile(tmp_path, viewport=viewport))


@pytest.mark.parametrize(
    "data",
    [
        {"default": "p", "profiles": {"p": "https://shop.test"}},
        {"profiles": {"p": {"base_url": "https://shop.test"}}},
        {"default": "p"},
    ],
    ids=["profile-not-object", "no-default", "no-profiles"],
)
def test_malformed_environment_file_raises_value_error(tmp_path: Path, data: dict) -> None:
    path = tmp_path / "env.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_environment(path)
