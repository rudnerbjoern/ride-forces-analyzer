"""Native storage, executable naming and frozen external-process isolation."""

# cspell:words delenv

from pathlib import Path
import os

import pytest

from ride_forces_analyzer.runtime import paths as runtime_paths
from ride_forces_analyzer.storage.exports import default_database_path
from ride_forces_analyzer.rendering import encoding


@pytest.mark.parametrize(
    "system,configured,relative",
    [
        ("win32", "LOCALAPPDATA", "Ride Forces Analyzer"),
        ("linux", "XDG_DATA_HOME", "ride-forces-analyzer"),
        ("darwin", None, "Library/Application Support/Ride Forces Analyzer"),
    ],
)
def test_native_data_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    system: str,
    configured: str | None,
    relative: str,
) -> None:
    monkeypatch.setattr(runtime_paths.sys, "platform", system)

    def home(cls: type[Path]) -> Path:
        return tmp_path

    monkeypatch.setattr(Path, "home", classmethod(home))
    if configured is not None:
        monkeypatch.setenv(configured, str(tmp_path))
    expected = tmp_path / relative
    assert runtime_paths.data_directory() == expected
    assert default_database_path() == expected / "exports.sqlite3"
    assert not expected.exists()


def test_missing_windows_and_relative_xdg_paths_use_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def home(cls: type[Path]) -> Path:
        return tmp_path

    monkeypatch.setattr(Path, "home", classmethod(home))
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert runtime_paths.data_directory() == tmp_path / "AppData/Local/Ride Forces Analyzer"
    monkeypatch.setattr(runtime_paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "relative")
    assert runtime_paths.data_directory() == tmp_path / ".local/share/ride-forces-analyzer"


@pytest.mark.parametrize(
    "system,machine,target,encoder",
    [
        ("win32", "AMD64", "windows-x64", "ffmpeg.exe"),
        ("linux", "x86_64", "linux-x64", "ffmpeg"),
        ("darwin", "arm64", "macos-arm64", "ffmpeg"),
        ("darwin", "x86_64", "macos-x64", "ffmpeg"),
        ("linux", "aarch64", None, "ffmpeg"),
        ("other", "x86_64", None, "ffmpeg"),
    ],
)
def test_native_distribution_and_encoder(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    machine: str,
    target: str | None,
    encoder: str,
) -> None:
    monkeypatch.setattr(runtime_paths.sys, "platform", system)
    monkeypatch.setattr(runtime_paths.platform, "machine", lambda: machine)
    assert runtime_paths.runtime_target() == target
    assert runtime_paths.ffmpeg_name() == encoder


@pytest.mark.parametrize("original", [None, "/system/libraries"])
def test_frozen_linux_encoder_restores_loader_path(
    monkeypatch: pytest.MonkeyPatch,
    original: str | None,
) -> None:
    monkeypatch.setattr(encoding.sys, "platform", "linux")
    monkeypatch.setattr(encoding.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/frozen/internal")
    if original is None:
        monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    else:
        monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", original)
    environment = encoding.encoder_environment()
    assert environment.get("LD_LIBRARY_PATH") == original
    assert os.environ["LD_LIBRARY_PATH"] == "/frozen/internal"


def test_posix_frozen_encoder_and_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(encoding.sys, "platform", "linux")
    monkeypatch.setattr(encoding.sys, "frozen", True, raising=False)
    monkeypatch.setattr(encoding.sys, "executable", str(tmp_path / "application"))
    bundled = tmp_path / "ffmpeg"
    bundled.write_bytes(b"synthetic encoder")
    explicit = tmp_path / "chosen"
    explicit.write_bytes(b"synthetic encoder")
    assert encoding.find_ffmpeg() == bundled
    assert encoding.find_ffmpeg(explicit) == explicit
