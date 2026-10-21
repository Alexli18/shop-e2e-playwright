"""Run artifacts: screenshots and a JSON event log, attached to the Allure report."""

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import re
from typing import Any

import allure
from playwright.sync_api import Page

log = logging.getLogger(__name__)

_SECRET_KEY = re.compile(r"pass(word)?|secret|token", re.IGNORECASE)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


class RunArtifacts:
    """Collects screenshots and log events for one scenario run under `directory`."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events: list[dict[str, Any]] = []
        self._shots = 0

    def screenshot(self, page: Page, name: str) -> Path:
        self._shots += 1
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "page"
        path = self.directory / f"{self._shots:02d}-{slug}.png"
        page.screenshot(path=path, full_page=True)
        allure.attach.file(str(path), name=name, attachment_type=allure.attachment_type.PNG)
        return path

    def log(self, event: str, **details: Any) -> None:
        """Record an event; keys that look like secrets are dropped, never written."""
        safe = {key: value for key, value in details.items() if not _SECRET_KEY.search(key)}
        entry = {"time": datetime.now(UTC).isoformat(timespec="seconds"), "event": event, **safe}
        self.events.append(entry)
        log.info("%s %s", event, safe)

    def save_log(self, name: str = "run-log.json") -> Path:
        path = self.directory / name
        path.write_text(json.dumps(self.events, indent=2, default=_jsonable), encoding="utf-8")
        allure.attach.file(str(path), name=name, attachment_type=allure.attachment_type.JSON)
        return path
