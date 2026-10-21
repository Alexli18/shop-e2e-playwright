"""Refresh the committed sample run in reports/ with a full serial run: the HTML report, the JUnit XML and
reports/sample-run/ (the screenshots and run-log.json of one assignment case).

Usage: python scripts/refresh_sample_report.py [extra pytest args]

The JUnit file is post-processed to drop the machine's hostname; nothing else is changed."""

from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
JUNIT = ROOT / "reports/junit.xml"
SAMPLE = ROOT / "reports/sample-run"
SAMPLE_CASE = (
    ROOT / "artifacts/playwright/tests-e2e-test-shopping-flow-py-test-shopping-flow-computers-under-1500-chromium"
)


def scrub_hostname(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r' hostname="[^"]*"', "", text), encoding="utf-8")


def main(extra: list[str]) -> int:
    command = [
        sys.executable, "-m", "pytest", "tests", "--browser", "chromium",
        f"--junitxml={JUNIT.relative_to(ROOT)}", "--html=reports/report.html", "--self-contained-html",
        *extra,
    ]  # fmt: skip
    code = subprocess.call(command, cwd=ROOT)
    if JUNIT.is_file():
        scrub_hostname(JUNIT)
    if code == 0 and SAMPLE_CASE.is_dir():
        for path in [*SAMPLE_CASE.glob("*.png"), SAMPLE_CASE / "run-log.json"]:
            shutil.copy2(path, SAMPLE / path.name)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
