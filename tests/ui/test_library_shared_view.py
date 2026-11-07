"""Library browsing stays shared while recording windows remain independent."""

import subprocess
import sys


def test_library_view_is_shared_without_opening_other_recordings() -> None:
    program = """
from PySide6.QtCore import QSignalBlocker, QThreadPool
from PySide6.QtTest import QSignalSpy
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.runtime.instance import OpenRequest
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.ui.application import RecordingApplication
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until

app = RecordingApplication([])
store = LibraryStore()
store.initialize()
digests = []
for index in range(30):
    source = synthetic_source(name=f"Ride {index:02d}", location="Park A" if index < 20 else "Park B")
    _, digest = store.archive(source, "ride.forces", (2, 6), CalibrationOverrides())
    digests.append(digest)
    if index % 2 == 0:
        store.set_workflow_status(digest, "completed")
app.start(OpenRequest())
first = app.windows[0]
first.open_archived(digests[0])
wait_until(lambda: first.data is not None and first.open_action.isEnabled())
second = app.create_window()
second.open_archived(digests[1])
wait_until(lambda: second.data is not None and second.open_action.isEnabled())
first_data, second_data = first.data, second.data
a, b = first.library, second.library
a.toggle_button.setChecked(True)
b.toggle_button.setChecked(True)
opened_a, opened_b = QSignalSpy(a.open_requested), QSignalSpy(b.open_requested)
changes = QSignalSpy(app.library_view_changed)

def same_view():
    assert a.park_filter.currentData() == b.park_filter.currentData()
    assert a.workflow_filter.currentData() == b.workflow_filter.currentData()
    assert a.search.text() == b.search.text()
    assert tuple(a._items) == tuple(b._items)
    assert a.selected_entry == b.selected_entry
    assert first.data is first_data and second.data is second_data
    assert opened_a.count() == opened_b.count() == 0

a.park_filter.setCurrentIndex(a.park_filter.findData("Park A"))
same_view()
b.workflow_filter.setCurrentIndex(b.workflow_filter.findData("completed"))
same_view()
a.search.setText("Ride 0")
same_view()
assert len(a._items) == 6
# Stream Deck movement suppresses the panel's recording-open signals.
with QSignalBlocker(a):
    a.recordings.setCurrentItem(a._items[digests[4]])
a.notify_view_changed()
same_view()
assert b.selected_entry.source_sha256 == digests[4]
third = app.create_window()
assert third.library.selected_entry == a.selected_entry
assert third.library.search.text() == "Ride 0"
assert third.library.park_filter.currentData() == "Park A"
assert third.library.workflow_filter.currentData() == "completed"
assert third.data is None
# Hidden panels participate; empty results clear the common selection.
b.toggle_button.setChecked(False)
a.search.setText("no matching ride")
same_view()
assert not a._items and a.selected_entry is None
b.clear_filters.click()
same_view()
assert len(a._items) == 30 and not a.search.text()
# List updates retain the shared view, including newly available park options.
source = synthetic_source(name="Additional ride", location="Park C")
store.archive(source, "ride.forces", (2, 6), CalibrationOverrides())
a.refresh()
same_view()
assert len(b._items) == 31 and len(third.library._items) == 31
a.park_filter.setCurrentIndex(a.park_filter.findData("Park C"))
same_view()
assert len(b._items) == 1
b.clear_filters.click()
same_view()
b.toggle_button.setChecked(True)
wait_until(lambda: a.recordings.verticalScrollBar().maximum() > 0 and b.recordings.verticalScrollBar().maximum() > 0)
a.recordings.verticalScrollBar().setValue(5)
assert b.recordings.verticalScrollBar().value() == 5
b.recordings.verticalScrollBar().setValue(2)
assert a.recordings.verticalScrollBar().value() == 2
# GUI selection opens only in its originating window.
a.recordings.setCurrentItem(a._items[digests[6]])
wait_until(lambda: first.data is not first_data and first.open_action.isEnabled())
assert first.data.source.source_sha256 == digests[6]
assert second.data is second_data and third.data is None
assert opened_a.count() == 1 and opened_b.count() == 0
assert a.selected_entry == b.selected_entry == third.library.selected_entry
assert changes.count() < 50, changes.count()
for window in tuple(app.windows):
    window.close()
QThreadPool.globalInstance().waitForDone()
app.processEvents()
print("Shared Library filters, selection, scrolling and independent recordings passed")
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Shared Library filters, selection, scrolling" in result.stdout
