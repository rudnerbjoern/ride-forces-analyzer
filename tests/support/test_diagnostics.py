"""Support reports include safe system fields and bounded encoder results."""

from pathlib import Path
import subprocess

import pytest

from ride_forces_analyzer import __version__, diagnostics
from ride_forces_analyzer.cpu_resources import CpuResources


@pytest.mark.parametrize("state", ["available", "missing", "failure", "timeout"])
def test_diagnostics_encoder_status_and_privacy(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    def find() -> Path:
        if state == "missing":
            raise ValueError("Private user path")
        return Path("private-user/ffmpeg")

    def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert arguments[-1] == "-version"
        assert kwargs["timeout"] == 3
        if state == "timeout":
            raise subprocess.TimeoutExpired(arguments, 3, output="Private user path")
        return subprocess.CompletedProcess(
            arguments,
            1 if state == "failure" else 0,
            "ffmpeg version 8.1-custom-private-user\nconfiguration: /private/user",
            "private error path",
        )

    monkeypatch.setattr(diagnostics, "find_ffmpeg", find)
    monkeypatch.setattr(diagnostics, "detect_cpu_resources", lambda: CpuResources(12, 24))
    monkeypatch.setattr(diagnostics.subprocess, "run", run)
    report = diagnostics.collect_diagnostics()
    assert f"Ride Forces Analyzer: {__version__}" in report
    assert "Physical CPU cores: 12" in report
    assert "Logical processors: 24" in report
    for field in ("Operating system", "Architecture", "Python", "Qt", "Distribution"):
        assert f"{field}: " in report
    expected = {"available": "Available", "missing": "Not found"}.get(state, "Check failed")
    assert f"FFmpeg: {expected}" in report
    if state == "available":
        assert "FFmpeg version: 8.1" in report
    assert "private" not in report.lower()
