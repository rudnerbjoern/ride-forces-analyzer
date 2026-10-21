"""Native CSV selection, worker lifetime and non-destructive publication."""

# cspell:words Abbrechen

from collections.abc import Callable
import csv
from pathlib import Path
from threading import Event

from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QWidget
import pytest

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.ui import csv_export as csv_ui, loading
from ride_forces_analyzer.ui.csv_export import CsvExportDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


@pytest.fixture(scope="module")
def recording() -> ExplorerData:
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Taron-*.forces")))
    assert isinstance(data, ExplorerData)
    return data


def test_csv_uses_selected_snapshot_range_and_remembers_only_success(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    assert not window.csv_button.isEnabled()

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/csv-recording.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.csv_button.isEnabled()
    window.first.setValue(5)
    window.last.setValue(8)
    window.reference_toggle.setChecked(False)
    original = recording.source.recording.source.original_bytes
    selected = ""
    suggestions: list[Path] = []

    def choose(*args: object, **kwargs: object) -> tuple[str, str]:
        assert isinstance(args[2], str)
        suggestions.append(Path(args[2]))
        return selected, ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    window.csv_button.click()
    assert window.csv_window is None
    assert window.preferences.export_directory() == ""
    selected = str(export_directory / "selected-samples")
    window.set_ui_language(1)
    window.toggle_playback()
    window.csv_button.click()
    assert not window.playback_timer.isActive()
    dialog = window.csv_window
    assert isinstance(dialog, CsvExportDialog)
    cancel_button = dialog.findChild(QPushButton)
    assert cancel_button is not None and cancel_button.text() == "Abbrechen"
    assert dialog.worker.analysis is recording.analysis
    assert dialog.worker.first == 5 and dialog.worker.last == 8
    wait_until(lambda: not dialog.isVisible())
    output = export_directory / "selected-samples.csv"
    with output.open(encoding="utf-8-sig", newline="") as stream:
        result = list(csv.DictReader(stream))
    assert [int(row["sample_index"]) for row in result] == [5, 6, 7, 8]
    assert all(row["smoothing_window_samples"] == "11" for row in result)
    assert all(row["Vertical Forces (g)"] != "" for row in result)
    assert window.preferences.export_directory() == str(export_directory.resolve())
    assert str(output) in window.statusBar().currentMessage()
    assert (window.first.value(), window.last.value()) == (5, 8)
    assert recording.source.recording.source.original_bytes == original
    previous = output.read_bytes()
    warnings: list[str] = []

    def warn(parent: QWidget, title: str, message: str) -> QMessageBox.StandardButton:
        warnings.append(message)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", warn)
    selected = str(output)
    window.csv_button.click()
    wait_until(lambda: bool(warnings))
    assert suggestions[-1].parent.resolve() == export_directory.resolve()
    assert output.read_bytes() == previous
    assert window.preferences.export_directory() == str(export_directory.resolve())


@pytest.mark.parametrize("close_parent", [False, True], ids=["cancel-button", "close-window"])
def test_csv_cancellation_keeps_the_worker_snapshot_and_cleans_up(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    close_parent: bool,
) -> None:
    window = explorer_window

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/csv-recording.forces"))
    wait_until(window.open_action.isEnabled)
    output = export_directory / "cancelled.csv"

    def choose(*args: object, **kwargs: object) -> tuple[str, str]:
        return str(output), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    started, release, finished = Event(), Event(), Event()
    original_export = csv_ui.export_csv

    def controlled_export(
        analysis: RecordingAnalysis,
        path: Path,
        first: int,
        last: int,
        *,
        cancelled: Callable[[], bool],
        progress: Callable[[int], None],
    ) -> int:
        started.set()
        try:
            if not release.wait(5):
                raise TimeoutError("CSV test worker was not released")
            return original_export(
                analysis,
                path,
                first,
                last,
                cancelled=cancelled,
                progress=progress,
            )
        finally:
            finished.set()

    monkeypatch.setattr(csv_ui, "export_csv", controlled_export)
    try:
        window.csv_button.click()
        wait_until(started.is_set)
        dialog = window.csv_window
        assert isinstance(dialog, CsvExportDialog)
        assert dialog.worker.analysis is recording.analysis
        if close_parent:
            window.close()
        else:
            button = dialog.findChild(QPushButton)
            assert button is not None
            button.click()
        assert dialog.worker.cancelled.is_set()
    finally:
        release.set()
    wait_until(finished.is_set)
    wait_until(lambda: not dialog.isVisible())
    assert not output.exists()
    assert window.preferences.export_directory() == ""
