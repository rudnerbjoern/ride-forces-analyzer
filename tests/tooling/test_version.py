"""Published application version."""

from ride_forces_analyzer import __version__
from pathlib import Path
import tomllib

import pytest

from scripts import generate_app_screenshots


def test_version() -> None:
    with (Path(__file__).resolve().parents[2] / "pyproject.toml").open("rb") as stream:
        project_version = tomllib.load(stream)["project"]["version"]
    assert __version__ == project_version


def test_screenshot_capture_rejects_a_mismatched_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generate_app_screenshots, "__version__", "0.0.0")
    with pytest.raises(ValueError, match="Screenshot version .* differs from project version"):
        generate_app_screenshots.capture_reference(tmp_path / "images")
    assert not (tmp_path / "images").exists()
