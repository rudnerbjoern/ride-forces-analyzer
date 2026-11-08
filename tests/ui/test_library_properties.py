"""Park choices support direct selection, completion and freely saved names."""

# cspell:words Phantasialand PHAN

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until


def test_properties_park_choices_completion_and_free_text(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    store = LibraryStore()
    source = synthetic_source(name="Selected ride", location="Source park")
    for item in (
        source,
        synthetic_source(name="Other ride", location="Europa-Park"),
        synthetic_source(name="Duplicate park", location="europa-park"),
        synthetic_source(name="Another ride", location="Phantasialand"),
    ):
        store.archive(item, "ride.forces", (2, 6), CalibrationOverrides())
    window.open_archived(source.source_sha256)
    wait_until(window.open_action.isEnabled)
    window.library.edit_action.trigger()
    editor = window.library.editor
    park = editor.park
    assert park.isEditable()
    assert tuple(park.itemText(index) for index in range(park.count())) == store.parks()
    assert park.count() == 3
    assert (
        park.currentText() == "" and editor.fields["park_name"].placeholderText() == "Source park"
    )

    wait_until(editor.isActiveWindow)
    editor.grab().save(".tmp/properties-park.png")
    QTest.mouseClick(
        park,
        Qt.MouseButton.LeftButton,
        pos=QPoint(park.width() - 8, park.height() // 2),
    )
    wait_until(park.view().isVisible)
    assert park.view().isVisible()
    park.view().grab().save(".tmp/properties-park-dropdown.png")
    QTest.keyClick(park.view(), Qt.Key.Key_Home)
    QTest.keyClick(park.view(), Qt.Key.Key_Return)
    assert park.currentText() == "Europa-Park"
    editor.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    additions = store.metadata(source.source_sha256)
    assert additions is not None and additions.park_name is None

    window.library.edit_action.trigger()
    field = editor.fields["park_name"]
    field.setFocus()
    QTest.keyClicks(field, "PHAN")
    completer = park.completer()
    assert completer is not None
    popup = completer.popup()
    assert popup is not None
    wait_until(popup.isVisible)
    popup.grab().save(".tmp/properties-park-completion.png")
    popup_window = popup.window().windowHandle()
    assert popup_window is not None
    QTest.keyClick(popup_window, Qt.Key.Key_Return)
    assert park.currentText() == "Phantasialand" and editor.isVisible()
    assert store.metadata(source.source_sha256) == additions
    editor.grab().save(".tmp/properties-park.png")
    editor.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    wait_until(window.open_action.isEnabled)
    additions = store.metadata(source.source_sha256)
    assert additions is not None and additions.park_name == "Phantasialand"

    window.library.edit_action.trigger()
    assert park.currentText() == "Phantasialand"
    field.selectAll()
    QTest.keyClicks(field, "New park")
    editor.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    wait_until(window.open_action.isEnabled)
    window.library.edit_action.trigger()
    assert park.currentText() == "New park" and park.findText("New park") >= 0
    field.clear()
    editor.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    wait_until(window.open_action.isEnabled)
    additions = store.metadata(source.source_sha256)
    assert additions is not None and additions.park_name is None

    for number in range(park.maxVisibleItems() + 1):
        store.archive(
            synthetic_source(name=f"Ride {number}", location=f"Park {number}"),
            "ride.forces",
            (2, 6),
            CalibrationOverrides(),
        )
    window.library.edit_action.trigger()
    assert park.count() > park.maxVisibleItems()
    assert park.currentText() == "" and field.placeholderText() == "Source park"
    field.setFocus()
    QTest.keyClicks(field, "park 10")
    wait_until(popup.isVisible)
    QTest.keyClick(popup_window, Qt.Key.Key_Return)
    assert park.currentText() == "Park 10" and editor.isVisible()
    editor.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert store.metadata(source.source_sha256) == additions
    archived = store.source(source.source_sha256)
    assert archived.data == source.recording.source.original_bytes
