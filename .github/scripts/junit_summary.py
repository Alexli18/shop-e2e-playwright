"""Append a JUnit summary table to the GitHub Actions job summary.

Usage: python .github/scripts/junit_summary.py "<title>" [artifacts/reports/junit.xml]
"""

import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def summary(title: str, path: Path) -> str:
    lines = [f"### {title}"]
    if not path.is_file():
        return "\n".join([*lines, "No JUnit report was produced."]) + "\n"
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    counts = {
        key: int(suite.get(key, 0)) if suite is not None else 0 for key in ("tests", "failures", "errors", "skipped")
    }
    passed = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    seconds = float(suite.get("time", 0)) if suite is not None else 0.0
    lines += [
        "| tests | passed | failed | errors | skipped | time (s) |",
        "|---|---|---|---|---|---|",
        f"| {counts['tests']} | {passed} | {counts['failures']} | {counts['errors']} | {counts['skipped']} "
        f"| {seconds:.0f} |",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    text = summary(sys.argv[1], Path(sys.argv[2] if len(sys.argv) > 2 else "artifacts/reports/junit.xml"))
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
