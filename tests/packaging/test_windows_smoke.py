"""Exercise the release self-test against the current desktop interface."""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from scripts import windows_smoke

from ride_forces_analyzer import __version__
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_windows_entry_self_test_imports_and_renders_with_german_light_settings() -> None:
    recording = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")).resolve()
    with TemporaryDirectory(dir=".tmp") as temporary:
        root = Path(temporary).resolve()
        report = root / "self-test.json"
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = str(root / "preferences")
        if sys.platform == "win32":
            environment["QT_QPA_PLATFORM"] = "windows"
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.windows_entry",
                "--self-test",
                str(report),
                "--recording",
                str(recording),
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        diagnostics = report.read_text(encoding="utf-8") if report.is_file() else ""
        assert process.returncode == 0, diagnostics + process.stdout + process.stderr
        result = json.loads(diagnostics)
        assert result["version"] == __version__
        assert result["passed"] and result["gui"] and result["german_light"]
        assert result["samples"] == 9638 and result["render"]
        assert "pdf_plugin_absent" not in result


def test_frozen_self_test_rejects_pdf_plugin(
    monkeypatch: pytest.MonkeyPatch,
    export_directory: Path,
) -> None:
    monkeypatch.setattr(windows_smoke.sys, "frozen", True, raising=False)
    monkeypatch.setattr(windows_smoke, "QApplication", Mock(return_value=Mock()))
    monkeypatch.setattr(windows_smoke.QImageReader, "supportedImageFormats", lambda: [b"pdf"])
    report = export_directory / "self-test.json"

    with pytest.raises(AssertionError):
        windows_smoke.smoke_test(report, None, False)

    result = json.loads(report.read_text(encoding="utf-8"))
    assert not result["passed"]
    assert "pdf_plugin_absent" not in result
    assert "AssertionError" in result["error"]
