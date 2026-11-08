"""Independent recording windows share only application preferences."""

# cspell:words Importieren importieren neuem Fenster öffnen

import subprocess
import sys

import pytest

from tests.support.recordings import REAL_FIXTURE_DIRECTORY


@pytest.mark.skip(reason="Native access violation in the multi-window scenario.")
def test_compare_windows_route_files_and_keep_independent_state() -> None:
    taron = next(REAL_FIXTURE_DIRECTORY.glob("Taron*.forces")).resolve()
    manta = next(REAL_FIXTURE_DIRECTORY.glob("Manta*.zforces")).resolve()
    program = """
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QFileDialog, QMessageBox
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.runtime.instance import OpenRequest
from ride_forces_analyzer.storage.library import LibraryStore, default_database_path
from ride_forces_analyzer.storage.library_history import LibraryHistory
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.ui.application import RecordingApplication
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until
import sqlite3
recoveries = []
original_interrupt_running = LibraryHistory.interrupt_running
def interrupt_running(history):
    recoveries.append(history.store.path)
    original_interrupt_running(history)
LibraryHistory.interrupt_running = interrupt_running
app = RecordingApplication([])
app.settings = AppSettings(language=Language.ENGLISH)
original_create_window = app.create_window
def create_window(*args, **kwargs):
    assert default_database_path().is_file()
    with sqlite3.connect(default_database_path()) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() is not None
    db.close()
    return original_create_window(*args, **kwargs)
app.create_window = create_window
app.start(OpenRequest(path=sys.argv[1]))
first = app.windows[0]
wait_until(lambda: first.data is not None and first.open_action.isEnabled())
original = first.data.analysis
first.preferences.remember_restore_last_file(True)
QFileDialog.getOpenFileNames = lambda *args, **kwargs: ([sys.argv[2]], "")
first.new_window_action.trigger()
wait_until(lambda: len(app.windows) == 2)
second = app.windows[1]
wait_until(lambda: second.data is not None and second.open_action.isEnabled())
assert first.data.analysis is original
assert first.data.source.source_sha256 != second.data.source.source_sha256
assert first.analysis_controller is not second.analysis_controller
assert first.navigation.playback is not second.navigation.playback
sample = second.navigation.slider.value()
first.navigation.slider.setValue(first.navigation.slider.value() + 1)
assert second.navigation.slider.value() == sample
second_range = (second.plot.axis_x.min(), second.plot.axis_x.max())
first.plot.axis_x.setRange(first.plot.axis_x.min() + 1, first.plot.axis_x.max() - 1)
assert (second.plot.axis_x.min(), second.plot.axis_x.max()) == second_range
app.receive_request(OpenRequest(path=sys.argv[1]))
assert len(app.windows) == 2
wait_until(first.open_action.isEnabled)
assert first.data.analysis is original
assert first.data.source.source_sha256 == original.source.source_sha256
first.set_ui_language(1)
assert all(window.ui_language == "de" for window in app.windows)
assert second.new_window_action.text() == "In neuem Fenster importieren …"
first.set_appearance(1)
assert first.theme is second.theme
# Explicit new windows do not restore the previously opened recording.
first._preview_appearance(2)
app.receive_request(OpenRequest(new_window=True))
blank = app.windows[-1]
app.processEvents()
assert blank.data is None and blank.recording_path is None
assert blank.theme is first.theme is second.theme
first._preview_appearance(1)
assert blank.close()
assert len(app.windows) == 2
# An explicit new-window request for an open file activates its existing window.
app.receive_request(OpenRequest(path=sys.argv[1], new_window=True))
assert len(app.windows) == 2
assert app.activeWindow() is first
assert first.data.analysis is original
# Library windows load archived bytes with saved edits, without any external path.
source = synthetic_source(name="Archived ride", location="Library park")
store = LibraryStore()
store.archive(source, "archived.forces", (2, 6), CalibrationOverrides())
store.update_metadata(source.source_sha256, {"ride_name": "Edited archive"})
with TemporaryDirectory(dir=".tmp") as directory:
    path = Path(directory) / "archived.forces"
    path.write_bytes(source.recording.source.original_bytes)
    first.open_path(path)
    wait_until(first.open_action.isEnabled)
first.library.toggle_button.click()
tree = first.library.recordings
group = tree.topLevelItem(0)
assert group is not None
item = None
for day in range(tree.topLevelItemCount()):
    group = tree.topLevelItem(day)
    for row in range(group.childCount()):
        candidate = group.child(row)
        if candidate.data(0, Qt.ItemDataRole.UserRole) == source.source_sha256:
            item = candidate
assert item is not None
tree.setCurrentItem(item)
wait_until(lambda: first.data is not None and first.open_action.isEnabled())
current = first.data
assert current.title == "Edited archive"
first.plot.axis_x.setRange(0.04, 0.1)
first.navigation.slider.setValue(3)
first_range = (first.plot.axis_x.min(), first.plot.axis_x.max())
first.library.new_window_action.trigger()
assert len(app.windows) == 3
archived = app.windows[-1]
wait_until(lambda: archived.data is not None and archived.open_action.isEnabled())
assert archived is not first and archived.recording_path is None
assert archived.data.title == "Edited archive"
assert archived.data.source.source_sha256 == source.source_sha256
assert archived.data.source.recording.source.original_bytes == source.recording.source.original_bytes
assert archived.data.ride_bounds == (2, 6)
assert archived.analysis_controller is not first.analysis_controller
assert archived.data.analysis is not current.analysis
assert archived.navigation.playback is not first.navigation.playback
assert archived.ui_language == first.ui_language and archived.theme is first.theme
assert first.data is current and first.navigation.slider.value() == 3
assert (first.plot.axis_x.min(), first.plot.axis_x.max()) == first_range
# Removal publishes one change to all Library subscribers, retaining loaded views.
archived.library.toggle_button.click()
changes = QSignalSpy(app.library_changed)
loads = QSignalSpy(first.library.open_requested)
archived_data = archived.data
def remove(answer):
    def respond():
        box = app.activeModalWidget()
        assert isinstance(box, QMessageBox)
        box.button(answer).click()
    QTimer.singleShot(0, respond)
    archived.library.remove_action.trigger()
remove(QMessageBox.StandardButton.No)
assert changes.count() == 0
assert first.library.selected_entry.source_sha256 == source.source_sha256
with store.connection() as db:
    db.execute("CREATE TRIGGER reject_removal BEFORE DELETE ON recordings "
               "BEGIN SELECT RAISE(ABORT, 'injected removal failure'); END")
remove(QMessageBox.StandardButton.Yes)
assert changes.count() == 0
assert first.library.selected_entry.source_sha256 == source.source_sha256
with store.connection() as db:
    db.execute("DROP TRIGGER reject_removal")
remove(QMessageBox.StandardButton.Yes)
assert changes.count() == 1 and changes.at(0) == [archived.library]
assert first.library.selected_entry is None and archived.library.selected_entry is None
for window in app.windows:
    assert not window.library.recordings.findItems(
        "Edited archive", Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive, 0)
assert loads.count() == 0 and first.data is current and archived.data is archived_data
assert first.navigation.slider.value() == 3
assert (first.plot.axis_x.min(), first.plot.axis_x.max()) == first_range
assert archived.close()
# Multiple imports archive all inputs and open only the first successful result.
with TemporaryDirectory(dir=".tmp") as directory:
    paths = tuple(Path(directory) / name for name in ("one.forces", "two.forces", "bad.forces"))
    for path, name in zip(paths[:2], ("Batch one", "Batch two")):
        path.write_bytes(synthetic_source(name=name).recording.source.original_bytes)
    paths[2].write_bytes(b"invalid recording")
    ordered = (paths[2], paths[0], paths[1])
    first.import_paths(ordered)
    wait_until(first.open_action.isEnabled)
    assert len(app.windows) == 2 and first.data.title == "Batch one"
    assert first.data.source.recording.source.provenance.path is None
    assert {"Batch one", "Batch two"} <= {entry.ride_name for entry in store.entries()}
    assert "bad.forces" in first.library.details.toPlainText()
    assert "bad.forces" in first.statusBar().currentMessage()
    # The explicit new-window option also reuses a recording that is already open.
    retained = first.data
    first.import_paths(ordered, new_window=True)
    wait_until(first.open_action.isEnabled)
    assert len(app.windows) == 2 and app.activeWindow() is first
    assert first.data is retained
    first.import_paths((paths[2], paths[2]))
    wait_until(first.open_action.isEnabled)
    assert len(app.windows) == 2 and first.data is retained
assert first.close()
assert len(app.windows) == 1 and second.data is not None
assert second.close()
QThreadPool.globalInstance().waitForDone()
app.processEvents()
assert len(recoveries) == 1
print("Independent recording windows passed")
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(taron), str(manta)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Independent recording windows passed" in result.stdout


def test_library_initialization_failure_prevents_first_window() -> None:
    program = """
from contextlib import closing
import sqlite3
from ride_forces_analyzer.runtime.instance import OpenRequest
from ride_forces_analyzer.storage.library import LibraryStoreError, default_database_path
from ride_forces_analyzer.ui.application import RecordingApplication
path = default_database_path()
path.parent.mkdir(parents=True, exist_ok=True)
with closing(sqlite3.connect(path)) as db, db:
    db.execute("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
    db.execute("INSERT INTO alembic_version VALUES ('99_0')")
original = path.read_bytes()
app = RecordingApplication([])
try:
    app.start(OpenRequest())
except LibraryStoreError:
    pass
else:
    raise AssertionError("Unsupported Library revision was accepted")
assert not app.windows and not app.ready
assert path.read_bytes() == original
print("Library startup failure preserved database and prevented window creation")
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Library startup failure preserved database" in result.stdout


def test_repeated_recording_opens_activate_one_window_without_reloading() -> None:
    program = """
from pathlib import Path
from tempfile import TemporaryDirectory
from PySide6.QtCore import QEvent, QThreadPool
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.runtime.instance import OpenRequest
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.ui.application import RecordingApplication
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until

app = RecordingApplication([])
app.settings = AppSettings()
try:
    app.start(OpenRequest(new_window=True))
    first = app.windows[0]
    store = LibraryStore()
    sources = [synthetic_source(name=name) for name in ("First ride", "Second ride")]
    for source in sources:
        store.archive(source, "ride.forces", (2, 6), CalibrationOverrides())
    first.open_archived(sources[0].source_sha256)
    wait_until(lambda: first.data is not None and first.open_action.isEnabled())
    initial = first.data
    first.navigation.slider.setValue(3)
    initial_view = first.plot.axis_x.min(), first.plot.axis_x.max()
    app._new_archive_window_requested(sources[0].source_sha256)
    assert len(app.windows) == 1 and app.activeWindow() is first
    assert first.data is initial and first.navigation.slider.value() == 3

    app._new_archive_window_requested(sources[1].source_sha256)
    second = app.windows[-1]
    assert second is not first
    for _ in range(5):
        app._new_archive_window_requested(sources[1].source_sha256)
        assert len(app.windows) == 2
    wait_until(lambda: second.data is not None and second.open_action.isEnabled())
    retained = second.data
    second.navigation.slider.setValue(4)
    for _ in range(5):
        second.showMinimized()
        app._new_archive_window_requested(sources[1].source_sha256)
        wait_until(lambda: app.activeWindow() is second and not second.isMinimized())
        assert len(app.windows) == 2 and second.data is retained
        assert second.navigation.slider.value() == 4
        assert first.data is initial and first.navigation.slider.value() == 3
        assert (first.plot.axis_x.min(), first.plot.axis_x.max()) == initial_view
    first.open_archived(sources[1].source_sha256)
    wait_until(lambda: app.activeWindow() is second)
    assert first.data is initial and second.data is retained
    first.open_archived(sources[0].source_sha256)
    wait_until(lambda: app.activeWindow() is first)
    assert first.data is initial and first.navigation.slider.value() == 3

    with TemporaryDirectory(dir=".tmp") as directory:
        path = Path(directory) / "same-recording.forces"
        path.write_bytes(sources[1].recording.source.original_bytes)
        first.open_path(path)
        wait_until(first.open_action.isEnabled)
        assert first.data is initial and second.data is retained
        assert app.activeWindow() is second
        app.receive_request(OpenRequest(path=str(path), new_window=True))
        wait_until(lambda: len(app.windows) == 2)
        assert app.activeWindow() is second and second.data is retained

        # Path requests also coalesce during loading and do not reload afterwards.
        third_source = synthetic_source(name="Third ride")
        external = Path(directory) / "third.forces"
        external.write_bytes(third_source.recording.source.original_bytes)
        app.receive_request(OpenRequest(path=str(external), new_window=True))
        third = app.windows[-1]
        app.receive_request(OpenRequest(path=str(external), new_window=True))
        assert len(app.windows) == 3
        wait_until(lambda: third.data is not None and third.open_action.isEnabled())
        third_data = third.data
        third.navigation.slider.setValue(3)
        for new_window in (False, True):
            app.receive_request(OpenRequest(path=str(external), new_window=new_window))
            assert len(app.windows) == 3 and third.data is third_data
            assert third.navigation.slider.value() == 3
            assert app.activeWindow() is third

        # Editing an already open ride must read saved values despite window reuse.
        editor = third.library.editor
        third.library.edit_action.trigger()
        assert editor.isVisible()
        values = {"ride_name": "Edited third", "park_name": "Edited park", "row": "Front",
                  "seat": "Left", "train": "Blue"}
        for key, value in values.items():
            editor.fields[key].setText(value)
        editor.notes.setPlainText("Saved notes")
        editor.position.setCurrentIndex(editor.position.findData("Seated"))
        editor.buttons.button(QDialogButtonBox.StandardButton.Save).click()
        assert not editor.isVisible()
        assert third.data is third_data
        assert "Edited third" in third.library.recordings.currentItem().text(0)
        third.library.edit_action.trigger()
        assert all(editor.fields[key].text() == value for key, value in values.items())
        assert editor.notes.toPlainText() == "Saved notes"
        assert editor.position.currentData() == "Seated"
        app.processEvents()
        editor.grab().save(".tmp/metadata-reopened-dialog.png")
        editor.notes.setPlainText("Second notes")
        editor.buttons.button(QDialogButtonBox.StandardButton.Save).click()
        third.library.edit_action.trigger()
        assert all(editor.fields[key].text() == value for key, value in values.items())
        assert editor.notes.toPlainText() == "Second notes"
        editor.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
        third.library.edit_action.trigger()
        editor.buttons.button(QDialogButtonBox.StandardButton.Reset).click()
        third.library.edit_action.trigger()
        assert all(not field.text() for field in editor.fields.values())
        assert not editor.notes.toPlainText() and editor.position.currentData() is None
        editor.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    print("Recording window reuse passed", flush=True)
finally:
    app.stream_deck.close()
    for window in app.windows[:]:
        window.close()
    QThreadPool.globalInstance().waitForDone()
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Recording window reuse passed" in result.stdout
