"""Single/data export histories and repeats use the existing native review/save flows."""

# cspell:words Exportverlauf Dauer

from pathlib import Path
from typing import Callable, cast
import json

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.exports.formats import DataExportFormat
from ride_forces_analyzer.rendering.encoding import ExportCancelled
from ride_forces_analyzer.rendering.model import (
    ExportSettings,
    ExportTimeline,
    StandardFrameRate,
    prepare_export,
)
from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress
from ride_forces_analyzer.storage.library_history import LibraryHistory
from ride_forces_analyzer.storage.library import LibraryStoreError
from ride_forces_analyzer.ui.explorer.library_exports import LibraryExportsDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.ui.exports.data import DataWorker
from ride_forces_analyzer.ui.exports.workers import ExportWorker
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until

pytestmark = pytest.mark.usefixtures("small_preview_frames")


def test_history_review_and_repeat_keep_saved_values_and_overwrite_protection(
    explorer_window: ExplorerWindow,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    source = synthetic_source(name="Captured ride")
    path = export_directory / "recording.forces"
    path.write_bytes(source.recording.source.original_bytes)
    data = load_recording(path)
    assert isinstance(data, ExplorerData) and data.analysis is not None
    history = LibraryHistory()
    digest = data.source.source_sha256
    history.store.archive(data.source, path.name, data.ride_bounds, CalibrationOverrides())
    history.store.set_workflow_status(digest, "uploaded")
    settings = ExportSettings(fps=StandardFrameRate.FPS_59_94)
    timeline = prepare_export(data.analysis, settings, 2, 5)

    def export(timeline: ExportTimeline, destination: Path, **kwargs: object) -> Path:
        progress = cast(Callable[[ExportProgress], None], kwargs["progress"])
        progress(ExportProgress(ExportPhase.RENDERING, 1, timeline.frame_count, 0.1, True))
        destination.write_bytes(b"published video")
        return destination

    monkeypatch.setattr("ride_forces_analyzer.ui.exports.workers.export_video", export)
    first_output = export_directory / "first.mov"
    ExportWorker(timeline, first_output, Path("encoder.exe")).run()
    assert history.entries(digest)[0].status == "completed"
    assert history.entries(digest)[0].gpu_encoding == 1
    assert history.entries(digest)[0].file_size == first_output.stat().st_size
    video_entry = history.entries(digest)[0]
    for format in DataExportFormat:
        target = export_directory / (
            f"samples-{format.value}.csv"
            if format is DataExportFormat.CSV
            else f"samples-{format.value}.json"
        )
        DataWorker(data.analysis, target, 2, 5, format).run()
    csv_entry = next(entry for entry in history.entries(digest) if entry.kind == "csv")
    DataWorker(data.analysis, export_directory / "bad.suffix", 2, 5, DataExportFormat.CSV).run()

    def cancelled(*args: object, **kwargs: object) -> Path:
        raise ExportCancelled()

    monkeypatch.setattr("ride_forces_analyzer.ui.exports.workers.export_video", cancelled)
    ExportWorker(timeline, export_directory / "cancelled.mov", Path("encoder.exe")).run()
    assert history.entries(digest)[0].status == "cancelled"
    assert history.entries(digest)[1].status == "failed"
    assert len(history.entries(digest)) == 6
    monkeypatch.setattr("ride_forces_analyzer.ui.exports.workers.export_video", export)
    history.store.update_metadata(digest, {"ride_name": "Later name", "row": "Back"})
    history.store.update_markers(data.source, (3, 6), CalibrationOverrides(gravity_index=0))
    path.unlink()
    first_output.unlink()

    window.library.toggle_button.click()
    group = window.library.recordings.topLevelItem(0)
    assert group is not None
    item = group.child(0)
    assert item is not None
    window.library.recordings.setCurrentItem(item)
    wait_until(window.open_action.isEnabled)
    current = window.data
    window.library.history_button.click()
    dialog = window.findChild(LibraryExportsDialog)
    assert dialog is not None and dialog.isVisible()
    assert dialog.attempts.count() == 6

    def choose(attempt_id: int) -> None:
        for row in range(dialog.attempts.count()):
            from PySide6.QtCore import Qt

            if dialog.attempts.item(row).data(Qt.ItemDataRole.UserRole) == attempt_id:
                dialog.attempts.setCurrentRow(row)
                return
        raise AssertionError("Missing history entry")

    choose(video_entry.id)
    assert "Captured ride" in dialog.details.toPlainText()
    assert dialog.repeat.isEnabled()
    dialog.grab().save(".tmp/lib11-history-dark.png")

    def encoder(explicit: Path | None = None) -> Path:
        return Path("encoder.exe")

    monkeypatch.setattr("ride_forces_analyzer.ui.exports.video.find_ffmpeg", encoder)
    monkeypatch.setattr("ride_forces_analyzer.ui.exports.form.find_ffmpeg", encoder)
    dialog.repeat.click()
    wait_until(lambda: dialog.worker is None)
    review = dialog.export_dialog
    assert review is not None
    wait_until(lambda: review.pages.currentIndex() == 1)
    assert review.analysis.configuration == data.analysis.configuration
    assert review.data.source.effective_metadata.name == "Captured ride"
    assert review.form.settings().fps == "60000/1001"
    assert review.form.settings().layout == settings.layout
    assert review.first == 2 and review.last == 5
    repeated_output = export_directory / "repeated.mov"
    destination = repeated_output

    def save_name(*args: object, **kwargs: object) -> tuple[str, str]:
        return str(destination), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", save_name)
    review.start.click()
    wait_until(lambda: review.worker is None)
    assert repeated_output.read_bytes() == b"published video"
    assert len(history.entries(digest)) == 7
    repeated_entry = history.entries(digest)[0]
    assert repeated_entry.status == "completed" and repeated_entry.id != video_entry.id
    assert repeated_entry.snapshot_json is not None
    assert (
        json.loads(repeated_entry.snapshot_json)["recording_metadata"]["ride_name"]
        == "Captured ride"
    )
    review.reject()
    wait_until(lambda: dialog.attempts.count() == 7)
    choose(csv_entry.id)
    repeated_csv = export_directory / "repeated.csv"
    destination = repeated_csv
    dialog.repeat.click()
    wait_until(lambda: repeated_csv.is_file())
    wait_until(lambda: dialog.attempts.count() == 8)
    assert len(history.entries(digest)) == 8
    before = repeated_csv.read_bytes()

    def decline(*args: object, **kwargs: object) -> QMessageBox.StandardButton:
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", decline)
    choose(csv_entry.id)
    dialog.repeat.click()
    wait_until(lambda: dialog.worker is None)
    assert repeated_csv.read_bytes() == before and len(history.entries(digest)) == 8
    window.set_ui_language(1)
    window.set_appearance(1)
    assert dialog.windowTitle() == "Exportverlauf…"
    assert "Dauer:" in dialog.details.toPlainText()
    dialog.grab().save(".tmp/lib11-history-light.png")
    window.set_ui_language(0)
    unsupported = json.loads(video_entry.snapshot_json or "{}")
    unsupported["schema_version"] = 999
    with history.store.connection() as connection:
        connection.execute(
            "UPDATE export_history SET export_snapshot_json=? WHERE id=?",
            (json.dumps(unsupported), video_entry.id),
        )
    dialog.refresh()
    choose(video_entry.id)
    assert not dialog.repeat.isEnabled() and dialog.error.isVisible()
    dialog.reject()
    assert window.data is current
    assert history.store.entries()[0].workflow_status == "uploaded"

    def fail_history(*args: object, **kwargs: object) -> None:
        raise LibraryStoreError("Injected history failure")

    monkeypatch.setattr(LibraryHistory, "finish", fail_history)
    safe_output = export_directory / "history-failed.mov"
    worker = ExportWorker(timeline, safe_output, Path("encoder.exe"))
    messages: list[str] = []
    worker.signals.finished.connect(messages.append)
    worker.run()
    assert safe_output.read_bytes() == b"published video"
    assert messages and "Saved" in messages[0] and "history could not be saved" in messages[0]
    safe_data = export_directory / "history-failed.csv"
    data_worker = DataWorker(data.analysis, safe_data, 2, 5, DataExportFormat.CSV)
    warnings: list[str] = []
    data_worker.signals.warning.connect(warnings.append)
    data_worker.run()
    assert safe_data.is_file() and warnings and "history could not be saved" in warnings[0]
