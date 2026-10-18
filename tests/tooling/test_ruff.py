import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("source", "expected_codes"),
    [("import os\n", ["F401"]), ("items = [\n    1,\n    2\n]\n", ["COM812"])],
)
def test_ruff_reports_lint_errors(source: str, expected_codes: list[str]) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--output-format=json",
            "--stdin-filename",
            "src/lint_probe.py",
            "-",
        ],
        input=source.encode("utf-8"),
        cwd=ROOT,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    diagnostics = json.loads(result.stdout)
    assert sorted(item["code"] for item in diagnostics) == sorted(expected_codes)


@pytest.mark.parametrize(
    ("source", "expected_status"),
    [
        ("items=[1,2,3]\n", 1),
        ("items = [1, 2, 3]\n", 0),
        ("items = [1, 2, 3]\r\n", 1),
    ],
)
def test_ruff_checks_formatting(source: str, expected_status: int) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "--no-cache",
            "--stdin-filename",
            "src/format_probe.py",
            "-",
        ],
        input=source.encode("utf-8"),
        cwd=ROOT,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == expected_status, result.stderr
