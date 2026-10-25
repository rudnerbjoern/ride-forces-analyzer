"""Confirmed video replacement preserves existing output until encoding succeeds."""

from io import BytesIO
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering import encoding
from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress
from ride_forces_analyzer.rendering.model import ExportSettings, prepare_export


@pytest.mark.parametrize("outcome", ["success", "cancel", "encoder_error", "replace_error"])
def test_confirmed_replacement_preserves_original_until_publication(
    manta: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(prefer_gpu=False), 0, 0)
    destination = export_directory / "existing.mov"
    destination.write_bytes(b"original video")
    cancelled = Event()
    process = Mock(stdin=BytesIO())
    process.wait.return_value = 1 if outcome == "encoder_error" else 0
    process.poll.return_value = 0

    def start(arguments: list[str], **kwargs: object) -> Mock:
        Path(arguments[-1]).write_bytes(b"completed video")
        return process

    updates: list[ExportProgress] = []

    def progress(update: ExportProgress) -> None:
        updates.append(update)
        if update.phase is ExportPhase.COMPLETED:
            assert destination.read_bytes() == b"completed video"
            assert update.remaining_seconds is None
        else:
            assert destination.read_bytes() == b"original video"
        if update.phase is ExportPhase.FINALIZING:
            assert update.completed_frames == update.total_frames == 1
            assert update.remaining_seconds is None
        if outcome == "cancel" and update.completed_frames:
            cancelled.set()

    def fail_replace(source: Path, target: Path) -> Path:
        raise PermissionError("Destination is in use")

    monkeypatch.setattr(encoding, "effective_render_jobs", Mock(return_value=1))
    monkeypatch.setattr(encoding, "find_ffmpeg", Mock(return_value=Path(__file__)))
    monkeypatch.setattr(encoding, "supports_nvidia", Mock(return_value=False))
    monkeypatch.setattr(
        encoding,
        "render_region_bytes",
        Mock(return_value=(b"frame" for _ in range(1))),
    )
    monkeypatch.setattr(encoding.subprocess, "Popen", start)
    if outcome == "replace_error":
        monkeypatch.setattr(Path, "replace", fail_replace)

    if outcome == "success":
        assert (
            encoding.export_video(
                timeline,
                destination,
                overwrite=True,
                progress=progress,
                cancelled=cancelled,
            )
            == destination
        )
        assert destination.read_bytes() == b"completed video"
    else:
        error = (
            encoding.ExportCancelled
            if outcome == "cancel"
            else PermissionError
            if outcome == "replace_error"
            else RuntimeError
        )
        with pytest.raises(error):
            encoding.export_video(
                timeline,
                destination,
                overwrite=True,
                progress=progress,
                cancelled=cancelled,
            )
        assert destination.read_bytes() == b"original video"
    phases = [update.phase for update in updates]
    assert phases[:2] == [ExportPhase.PREPARING, ExportPhase.RENDERING]
    assert updates[0].use_gpu is None
    assert all(update.use_gpu is False for update in updates[1:])
    assert all(update.elapsed_seconds >= 0 for update in updates)
    assert (ExportPhase.COMPLETED in phases) == (outcome == "success")
    assert list(export_directory.iterdir()) == [destination]
