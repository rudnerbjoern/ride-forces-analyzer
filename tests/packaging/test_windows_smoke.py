"""Exercise the release self-test against the current desktop interface."""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

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
