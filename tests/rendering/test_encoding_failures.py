"""Encoder discovery and publication failures preserve files without real video work."""

# cspell:words EXDEV

from collections.abc import Generator
from dataclasses import replace
import errno
from io import BytesIO
from pathlib import Path
from threading import Event
from typing import BinaryIO, cast
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering import encoding
from ride_forces_analyzer.rendering.model import ExportSettings, ExportTimeline, prepare_export


@pytest.fixture
def timeline(manta: ExplorerData) -> ExportTimeline:
    assert manta.analysis is not None
    return prepare_export(manta.analysis, ExportSettings(prefer_gpu=False), 0, 0)


def test_encoder_discovery_precedence_and_missing_locations(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = export_directory / encoding.ffmpeg_name()
    with pytest.raises(ValueError, match="Choose an existing"):
        encoding.find_ffmpeg(executable)
    executable.write_bytes(b"encoder")
    assert encoding.find_ffmpeg(executable) == executable.resolve()
    monkeypatch.setattr(encoding.sys, "frozen", False, raising=False)
    system = export_directory / "system-encoder"
    monkeypatch.setattr(encoding.shutil, "which", Mock(return_value=str(system)))
    assert encoding.find_ffmpeg() == system
    monkeypatch.setattr(encoding.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        encoding.sys,
        "executable",
        str(export_directory / "application" / "analyzer.exe"),
    )
    assert encoding.find_ffmpeg() == system
    monkeypatch.setattr(encoding.shutil, "which", Mock(return_value=None))
    monkeypatch.chdir(export_directory)
    local = export_directory / ".tmp" / "ffmpeg" / "bin" / encoding.ffmpeg_name()
    local.parent.mkdir(parents=True)
    local.write_bytes(b"local encoder")
    assert encoding.find_ffmpeg() == local.resolve()
    local.unlink()
    with pytest.raises(ValueError, match="FFmpeg was not found"):
        encoding.find_ffmpeg()


def test_gpu_probe_failures_fall_back_to_cpu(
    timeline: ExportTimeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = replace(timeline, settings=replace(timeline.settings, prefer_gpu=True))
    for error in (OSError("Unavailable"), encoding.subprocess.TimeoutExpired("ffmpeg", 30)):
        monkeypatch.setattr(encoding.subprocess, "run", Mock(side_effect=error))
        assert not encoding.supports_nvidia(Path("ffmpeg.exe"), enabled)


@pytest.mark.parametrize(
    "mode",
    [
        "hard-link",
        "copy",
        "copy-cancel",
        "link-error",
        "empty-output",
        "missing-output",
        "broken-pipe",
        "render-and-close-error",
        "late-cancel",
        "probe-cancel",
        "wrong-extension",
        "startup-error",
    ],
)
def test_export_failures_cleanup_staging_and_never_publish_partial_output(
    timeline: ExportTimeline,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    destination = export_directory / ("video.mp4" if mode == "wrong-extension" else "video.mov")
    cancelled = Event()
    process = Mock(stdin=BytesIO())
    process.wait.return_value = 0
    process.poll.return_value = 0

    def frames(bound: ExportTimeline, jobs: int) -> Generator[bytes, None, None]:
        if mode == "render-and-close-error":
            raise ValueError("Renderer failed")
        yield b"frame"

    def probe(executable: Path, bound: ExportTimeline) -> bool:
        if mode == "probe-cancel":
            cancelled.set()
        return False

    def start(arguments: list[str], **kwargs: object) -> Mock:
        if mode == "startup-error":
            raise OSError("Encoder could not start")
        if mode != "missing-output":
            Path(arguments[-1]).write_bytes(b"" if mode == "empty-output" else b"encoded video")
        if mode == "broken-pipe":
            log = cast(BinaryIO, kwargs["stderr"])
            log.write(b"Encoder refused input")
            log.flush()
            process.stdin = Mock(closed=False)
            process.stdin.write.side_effect = BrokenPipeError("Closed pipe")
        if mode == "render-and-close-error":
            process.stdin = Mock(closed=False)
            process.stdin.close.side_effect = OSError("Close failed")
            process.poll.return_value = None
        if mode == "late-cancel":

            def finished(*, timeout: int) -> int:
                cancelled.set()
                return 0

            process.wait.side_effect = finished
        return process

    def unavailable_link(source: Path, target: Path) -> None:
        if mode == "copy-cancel":
            cancelled.set()
        raise OSError(errno.EACCES if mode == "link-error" else errno.EXDEV, "Link unavailable")

    monkeypatch.setattr(encoding, "find_ffmpeg", Mock(return_value=Path("ffmpeg.exe")))
    monkeypatch.setattr(encoding, "supports_nvidia", probe)
    monkeypatch.setattr(encoding, "render_region_bytes", frames)
    monkeypatch.setattr(encoding.subprocess, "Popen", start)
    if mode in ("copy", "copy-cancel", "link-error"):
        monkeypatch.setattr(encoding.os, "link", unavailable_link)
    if mode in ("hard-link", "copy"):
        assert (
            encoding.export_video(timeline, destination, cancelled=cancelled)
            == destination.resolve()
        )
        assert destination.read_bytes() == b"encoded video"
    else:
        error = (
            encoding.ExportCancelled
            if "cancel" in mode
            else ValueError
            if mode
            in (
                "wrong-extension",
                "render-and-close-error",
            )
            else OSError
            if mode in ("link-error", "startup-error")
            else RuntimeError
        )
        with pytest.raises(error):
            encoding.export_video(timeline, destination, cancelled=cancelled)
        assert not destination.exists()
    assert not list(export_directory.glob(".ride-forces-export-*"))
    if mode == "render-and-close-error":
        process.kill.assert_called_once()
