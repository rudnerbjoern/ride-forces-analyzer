"""Native CSV/JSON selection, worker lifetime and non-destructive publication."""

# cspell:words Abbrechen

from collections.abc import Callable
import csv
import json
from pathlib import Path
from threading import Event

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton, QWidget
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent

from ride_forces_analyzer.exports.formats import DataExportFormat
from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.ui.exports import data as data_ui
from ride_forces_analyzer.ui.explorer import loading
from ride_forces_analyzer.ui.exports.data import DataExportDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


@pytest.fixture(scope="module")
def recording() -> ExplorerData:
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Taron-*.forces")))
    assert isinstance(data, ExplorerData)
    return data


def test_data_uses_selected_snapshot_range_and_remembers_only_success(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    assert not window.data_export_button.isEnabled()

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/csv-recording.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.data_export_button.isEnabled()
    menu = window.data_export_button.menu()
    assert menu is not None and menu.actions() == [
        window.csv_action,
        window.json_action,
        window.analyzer_json_action,
    ]
    for appearance in (0, 1):
        window.set_appearance(appearance)
        menu.popup(
            window.data_export_button.mapToGlobal(QPoint(0, window.data_export_button.height())),
        )
        wait_until(menu.isVisible)
        try:
            for action in menu.actions():
                point = menu.actionGeometry(action).center()
                QApplication.sendEvent(
                    menu,
                    QMouseEvent(
                        QEvent.Type.MouseMove,
                        QPointF(point),
                        QPointF(menu.mapToGlobal(point)),
                        Qt.MouseButton.NoButton,
                        Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier,
                    ),
                )
                assert menu.activeAction() is action
                geometry = menu.actionGeometry(action)
                background = QPoint(geometry.right() - 8, geometry.center().y())
                assert menu.grab().toImage().pixelColor(background) == QColor(window.theme.accent)
        finally:
            menu.close()
    for format in DataExportFormat:
        action = {
            DataExportFormat.CSV: window.csv_action,
            DataExportFormat.JSON: window.json_action,
            DataExportFormat.ANALYZER_JSON: window.analyzer_json_action,
        }[format]
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
        previous_dialog = window.data_export_window
        previous_directory = window.preferences.export_directory()
        action.trigger()
        assert window.data_export_window is previous_dialog
        assert window.preferences.export_directory() == previous_directory
        selected = str(export_directory / f"selected-samples-{format}")
        window.set_ui_language(1)
        window.toggle_playback()
        action.trigger()
        assert not window.playback_timer.isActive()
        dialog = window.data_export_window
        assert isinstance(dialog, DataExportDialog)
        assert dialog.format is format and dialog.worker.format is format
        assert dialog.objectName() == f"{format.value}ExportProgress"
        cancel_button = dialog.findChild(QPushButton)
        assert cancel_button is not None and cancel_button.text() == "Abbrechen"
        assert dialog.worker.analysis is recording.analysis
        assert dialog.worker.first == 5 and dialog.worker.last == 8
        wait_until(lambda dialog=dialog: not dialog.isVisible())
        output = (
            export_directory
            / f"selected-samples-{format}.{'csv' if format is DataExportFormat.CSV else 'json'}"
        )
        with output.open(encoding="utf-8-sig", newline="") as stream:
            if format == DataExportFormat.CSV:
                result = list(csv.DictReader(stream))
                assert [int(row["sample_index"]) for row in result] == [5, 6, 7, 8]
                assert all(row["smoothing_window_samples"] == "11" for row in result)
                assert all(row["Vertical Forces (g)"] != "" for row in result)
            elif format == DataExportFormat.JSON:
                payload = json.load(stream)
                assert payload["sample_index"] == [5, 6, 7, 8]
                assert payload["metadata"]["smoothing_window_samples"] == 11
                assert all(value is not None for value in payload["Vertical Forces (g)"])
            else:
                payload = json.load(stream)
                assert payload["time"]["first_sample"] == 5
                assert payload["time"]["sample_count"] == 4
                assert payload["analysis"]["stages"]["smoothing"]["parameters"] == [
                    ["window_samples", 11],
                ]
                assert all(
                    value is not None for value in payload["samples"]["smoothed"]["vertical"]
                )
                assert suggestions[0].name.endswith(".analyzer.json")
        assert window.preferences.export_directory() == str(export_directory.resolve())
        assert str(output) in window.statusBar().currentMessage()
        assert (window.first.value(), window.last.value()) == (5, 8)
        assert recording.source.recording.source.original_bytes == original
        previous = output.read_bytes()
        questions: list[str] = []
        answer = QMessageBox.StandardButton.No

        def confirm(
            parent: QWidget,
            title: str,
            message: str,
            buttons: QMessageBox.StandardButton,
            default: QMessageBox.StandardButton,
        ) -> QMessageBox.StandardButton:
            assert buttons == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            assert default == QMessageBox.StandardButton.No
            questions.append(message)
            return answer

        monkeypatch.setattr(QMessageBox, "question", confirm)
        # Confirm the actual destination after automatic suffix completion.
        selected = str(output.with_suffix(""))
        for answer in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Cancel):
            action.trigger()
            assert str(output) in questions[-1]
            assert window.data_export_window is dialog
            assert output.read_bytes() == previous
        answer = QMessageBox.StandardButton.Yes
        window.first.setValue(6)
        window.last.setValue(7)
        action.trigger()
        replacement = window.data_export_window
        assert isinstance(replacement, DataExportDialog) and replacement is not dialog
        assert replacement.worker.overwrite
        wait_until(lambda replacement=replacement: not replacement.isVisible())
        assert suggestions[-1].parent.resolve() == export_directory.resolve()
        assert output.read_bytes() != previous
        with output.open(encoding="utf-8-sig", newline="") as stream:
            if format == DataExportFormat.CSV:
                assert [int(row["sample_index"]) for row in csv.DictReader(stream)] == [6, 7]
            elif format == DataExportFormat.JSON:
                assert json.load(stream)["sample_index"] == [6, 7]
            else:
                time = json.load(stream)["time"]
                assert time["first_sample"] == 6 and time["sample_count"] == 2
        assert window.preferences.export_directory() == str(export_directory.resolve())


def test_data_cancellation_keeps_the_worker_snapshot_and_cleans_up(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/csv-recording.forces"))
    wait_until(window.open_action.isEnabled)
    for format in DataExportFormat:
        close_parent = format is DataExportFormat.ANALYZER_JSON
        action = {
            DataExportFormat.CSV: window.csv_action,
            DataExportFormat.JSON: window.json_action,
            DataExportFormat.ANALYZER_JSON: window.analyzer_json_action,
        }[format]
        output = (
            export_directory / f"cancelled.{'csv' if format is DataExportFormat.CSV else 'json'}"
        )

        def choose(*args: object, **kwargs: object) -> tuple[str, str]:
            return str(output), ""

        monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
        started, release, finished = Event(), Event(), Event()
        original_export = {
            DataExportFormat.CSV: data_ui.export_csv,
            DataExportFormat.JSON: data_ui.export_json,
            DataExportFormat.ANALYZER_JSON: data_ui.export_analyzer_json,
        }[format]

        def controlled_export(
            analysis: RecordingAnalysis,
            path: Path,
            first: int,
            last: int,
            *,
            overwrite: bool,
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
                    overwrite=overwrite,
                    cancelled=cancelled,
                    progress=progress,
                )
            finally:
                finished.set()

        monkeypatch.setattr(data_ui, f"export_{format}", controlled_export)
        try:
            action.trigger()
            wait_until(started.is_set)
            dialog = window.data_export_window
            assert isinstance(dialog, DataExportDialog)
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
        wait_until(lambda dialog=dialog: not dialog.isVisible())
        assert not output.exists()
        assert window.preferences.export_directory() == ""
