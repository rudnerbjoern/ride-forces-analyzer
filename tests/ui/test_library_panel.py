"""Native Library interactions, explicit archive import and preserved chart state."""

# cspell:words Seaworld Uhrzeit Heure Importiert Importé Keine passenden Aufnahmen Tous Aucun enregistrement correspondant Metadaten bearbeiten métadonnées Abgeschlossen Terminé

from pathlib import Path
import json

from PySide6.QtWidgets import (
    QPlainTextEdit,
    QApplication,
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QLabel,
)
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QSignalSpy, QTest
import pytest

from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.ui.explorer.library_workflow import WorkflowIcon
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.storage.library import WORKFLOW_STATUSES
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.storage.preferences import Appearance
from ride_forces_analyzer.ui.dialogs.settings import APPEARANCE_CHOICES
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import resize_workspace, wait_until
from tests.analysis.test_recording_preparation import synthetic_source


def test_import_reveals_selected_recording_below_the_visible_list(
    explorer_window: ExplorerWindow,
    export_directory: Path,
) -> None:
    window = explorer_window
    library = window.library
    store = LibraryStore()
    for index in range(24):
        source = synthetic_source(name=f"Newer ride {index}", date=1_000_000)
        store.archive(source, "ride.forces", (2, 6), CalibrationOverrides())
    library.toggle_button.click()
    tree = library.recordings
    wait_until(lambda: tree.verticalScrollBar().maximum() > 0)
    tree.scrollToTop()
    first = synthetic_source(name="Older first ride", date=0)
    second = synthetic_source(name="Older second ride", date=86400)
    paths = (export_directory / "first.forces", export_directory / "second.forces")
    for path, source in zip(paths, (first, second), strict=True):
        path.write_bytes(source.recording.source.original_bytes)
    opened = QSignalSpy(library.open_requested)
    window.import_paths(paths)
    wait_until(window.open_action.isEnabled)
    QApplication.processEvents()
    item = tree.currentItem()
    assert item is not None and item.data(0, Qt.ItemDataRole.UserRole) == first.source_sha256
    assert tree.viewport().rect().contains(tree.visualItemRect(item))
    assert len(store.entries()) == 26 and opened.count() == 0

    # A reused entry is revealed even when the Library was collapsed during import.
    tree.scrollToTop()
    assert not tree.viewport().rect().contains(tree.visualItemRect(item))
    library.toggle_button.click()
    window.import_paths(paths)
    wait_until(window.open_action.isEnabled)
    current = window.data
    library.toggle_button.click()
    QApplication.processEvents()
    item = tree.currentItem()
    assert item is not None and item.data(0, Qt.ItemDataRole.UserRole) == first.source_sha256
    assert tree.viewport().rect().contains(tree.visualItemRect(item))
    assert window.data is current and opened.count() == 0


def test_library_toggle_preserves_workspace_and_recording(
    explorer_window: ExplorerWindow,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    assert not window.library.toggle_button.isChecked()
    assert not window.library.panel.isVisible()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    window.navigation.position.setValue(4000)
    window.inspector.first.setValue(3000)
    window.inspector.last.setValue(6000)
    window.plot.axis_x.setRange(60, 100)
    QApplication.processEvents()
    data = window.data
    minimum = window.minimumSizeHint()
    workspace_width = window.workspace.width()
    size = window.size()

    for language, caption in ((0, "Library"), (1, "Bibliothek"), (2, "Bibliothèque")):
        window.set_ui_language(language)
        QApplication.processEvents()
        window.library.toggle_button.click()
        QApplication.processEvents()
        assert window.library.panel.isVisible(), (
            language,
            window.library.toggle_button.isChecked(),
            window.library.toggle_button.isEnabled(),
            window.library.isVisible(),
            window.isVisible(),
        )
        assert window.library.toggle_button.text() == caption
        assert window.library.toggle_button.accessibleName() == caption
        assert window.library.toggle_button.toolTip() == caption
        assert window.library.panel.findChildren(QLabel)[0].text() == caption.upper()
        assert window.workspace.width() < workspace_width
        assert window.size() == size
        width = window.library.panel.width()
        window.library.setSizes([width + 40, window.workspace.width() - 40])
        QApplication.processEvents()
        assert window.library.panel.width() > width
        window.library.toggle_button.click()
        QApplication.processEvents()
        assert not window.library.panel.isVisible()
        assert window.workspace.width() == workspace_width
        assert window.data is data
        assert window.navigation.position.value() == 4000
        assert (window.inspector.first.value(), window.inspector.last.value()) == (3000, 6000)
        assert window.plot.axis_x.min() == pytest.approx(60)
        assert window.plot.axis_x.max() == pytest.approx(100)

    window.set_ui_language(0)
    QApplication.processEvents()
    assert window.minimumSizeHint() == minimum
    resize_workspace(window, 720, 480)
    compact_size = window.size()
    for _ in range(2):
        window.library.toggle_button.click()
        QApplication.processEvents()
        assert window.library.panel.isVisible() == window.library.toggle_button.isChecked()
        assert window.size() == compact_size

    # Every external open archives before loading; the toolbar also accepts multiple files.
    store = LibraryStore()
    with store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM recordings").fetchone() == (1,)
    resize_workspace(window, 1920, 1040)
    window.library.toggle_button.click()
    bad = export_directory / "bad.forces"
    bad.write_bytes(b"invalid JSON")
    paths = [str(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))), str(bad)]

    def choose(*args: object, **kwargs: object) -> tuple[list[str], str]:
        return paths, ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", choose)
    window.choose_file(new_window=True)
    wait_until(window.open_action.isEnabled)
    report = window.statusBar().currentMessage()
    assert "bad.forces: Import failed:" in report
    assert "bad.forces: Import failed:" in window.library.details.toPlainText()
    assert (
        window.library.panel.findChild(
            QPlainTextEdit,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        )
        is None
    )
    with store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM recordings").fetchone() == (1,)
    paths[:] = paths[:1]
    window.choose_file(new_window=True)
    wait_until(window.open_action.isEnabled)
    assert len(store.entries()) == 1
    paths.clear()
    window.choose_file(new_window=True)
    assert window.open_action.isEnabled()
    assert window.data is data
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == pytest.approx((60, 100))
    assert window.navigation.position.value() == 4000

    # Selection loads only an archived original through the normal load lifecycle.
    tree = window.library.recordings
    assert tree.topLevelItemCount() == 1
    day = tree.topLevelItem(0)
    assert day is not None and day.text(0) == "2026-09-17"
    assert not day.flags() & Qt.ItemFlag.ItemIsSelectable
    item = day.child(0)
    assert item is not None and item.text(0).splitlines() == [
        "Manta",
        "Seaworld Orlando",
        "10:17 · 0 exports",
    ]
    assert (
        tree.isHeaderHidden()
        and tree.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    status_icon = tree.itemWidget(item, 1)
    assert isinstance(status_icon, WorkflowIcon)
    assert item.toolTip(1) == "Imported" and not status_icon.button.icon().isNull()
    assert window.library.workflow_selector is None
    tree.setCurrentIndex(QModelIndex())
    tree.setCurrentItem(item)
    assert not tree.isEnabled()
    wait_until(window.open_action.isEnabled)
    assert tree.isEnabled() and window.data is not None and window.data is not data
    assert window.data.source.recording.source.provenance.path is None
    assert window.library.details.isReadOnly()
    details = " ".join(window.library.details.toPlainText().split())
    assert "Recording time: 2026-09-17 10:17" in details
    assert "America/New_York" not in details and "Source date:" not in details
    assert "Import time:" in details and "Row: 3" in details
    archived = window.data
    window.plot.axis_x.setRange(60, 100)
    window.navigation.position.setValue(4000)
    window.inspector.first.setValue(3000)
    window.inspector.last.setValue(6000)
    window.library.toggle_button.click()
    QApplication.processEvents()
    assert window.workspace.width() == workspace_width
    assert window.minimumSizeHint() == minimum
    window.library.toggle_button.click()
    current_item = tree.currentItem()
    assert current_item is not None and current_item.text(0).splitlines()[0] == "Manta"
    for language, status in ((1, "Importiert"), (2, "Importé"), (0, "Imported")):
        window.set_ui_language(language)
        assert current_item.toolTip(1) == status
        assert window.data is archived
        assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == pytest.approx((60, 100))
    with store.connection() as connection:
        connection.execute("UPDATE recordings SET workflow_status='markers_verified'")
    window.library.refresh()
    current_item = tree.currentItem()
    assert current_item is not None and current_item.toolTip(1) == "Markers verified"
    status_icon = tree.itemWidget(current_item, 1)
    assert isinstance(status_icon, WorkflowIcon)
    assert not status_icon.button.icon().isNull() and window.data is archived

    # Inline status selection never selects/reloads the recording or changes the chart.
    QApplication.processEvents()
    selected_item = tree.currentItem()
    viewport = (window.plot.axis_x.min(), window.plot.axis_x.max())
    row_rect = tree.visualItemRect(current_item)
    QTest.mouseClick(status_icon.button, Qt.MouseButton.LeftButton)
    selector = window.library.workflow_selector
    assert selector is not None
    wait_until(selector.isVisible)
    assert list(selector.buttons) == list(WORKFLOW_STATUSES)
    assert selector.buttons["markers_verified"].isChecked()
    assert selector.parentWidget() is window
    assert not selector.isWindow()
    assert current_item.childCount() == 0 and tree.visualItemRect(current_item) == row_rect
    assert selector.buttons["markers_verified"].mapTo(
        window,
        selector.buttons["markers_verified"].rect().center(),
    ) == status_icon.button.mapTo(window, status_icon.button.rect().center())
    xs = [selector.buttons[status].x() for status in WORKFLOW_STATUSES]
    assert xs == sorted(xs) and len(set(xs)) == 6
    window.grab().save(".tmp/lib08-workflow.png")
    QTest.keyClick(selector.buttons["markers_verified"], Qt.Key.Key_Escape)
    assert window.library.workflow_selector is None
    assert store.entries()[0].workflow_status == "markers_verified"
    QTest.mouseClick(status_icon.button, Qt.MouseButton.LeftButton)
    assert window.library.workflow_selector is not None
    QTest.mouseClick(window.library.search, Qt.MouseButton.LeftButton)
    assert window.library.workflow_selector is None
    QTest.mouseClick(status_icon.button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(status_icon.button, Qt.MouseButton.LeftButton)
    assert window.library.workflow_selector is None
    for status in (
        "completed",
        "imported",
        "video_ready",
        "overlays_created",
        "uploaded",
        "markers_verified",
    ):
        QTest.mouseClick(status_icon.button, Qt.MouseButton.LeftButton)
        selector = window.library.workflow_selector
        assert selector is not None
        wait_until(selector.isVisible)
        QTest.mouseClick(selector.buttons[status], Qt.MouseButton.LeftButton)
        assert window.library.workflow_selector is None
        assert store.entries()[0].workflow_status == status
        assert status_icon.button.toolTip() == current_item.toolTip(1)
    with store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_workflow BEFORE UPDATE OF workflow_status ON recordings "
            "BEGIN SELECT RAISE(ABORT, 'injected workflow failure'); END",
        )
    QTest.mouseClick(status_icon.button, Qt.MouseButton.LeftButton)
    selector = window.library.workflow_selector
    assert selector is not None
    wait_until(selector.isVisible)
    QTest.mouseClick(selector.buttons["completed"], Qt.MouseButton.LeftButton)
    assert window.library.workflow_selector is selector
    assert selector.buttons["markers_verified"].isChecked()
    assert status_icon.button.toolTip() == "Markers verified"
    assert "Could not save workflow status" in " ".join(
        window.library.details.toPlainText().split(),
    )
    with store.connection() as connection:
        connection.execute("DROP TRIGGER reject_workflow")
    for language, caption in ((1, "Abgeschlossen"), (2, "Terminé"), (0, "Completed")):
        window.set_ui_language(language)
        assert selector.buttons["completed"].toolTip() == caption
        assert selector.buttons["markers_verified"].isChecked()
    QTest.keyClick(selector.buttons["markers_verified"], Qt.Key.Key_Escape)
    assert tree.currentItem() is selected_item and window.data is archived
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == viewport
    for appearance in (Appearance.DARK, Appearance.LIGHT, Appearance.MANTA):
        QTest.mouseClick(status_icon.button, Qt.MouseButton.LeftButton)
        selector = window.library.workflow_selector
        assert selector is not None
        window.set_appearance(APPEARANCE_CHOICES.index(appearance))
        QApplication.processEvents()
        assert selector.buttons["markers_verified"].isChecked()
        assert selector.buttons["completed"].palette().color(
            QPalette.ColorRole.ButtonText,
        ) == status_icon.button.palette().color(QPalette.ColorRole.ButtonText)
        if appearance is Appearance.LIGHT:
            window.grab().save(".tmp/lib08-workflow-light.png")
        QTest.keyClick(selector.buttons["markers_verified"], Qt.Key.Key_Escape)
        heading = window.library.panel.findChild(QLabel, "SectionTitle")
        inspector_heading = window.inspector.findChildren(QLabel, "SectionTitle")[0]
        assert heading is not None and heading.font() == inspector_heading.font()
        assert heading.palette().color(
            QPalette.ColorRole.WindowText,
        ) == inspector_heading.palette().color(QPalette.ColorRole.WindowText)
        group = tree.topLevelItem(0)
        assert group is not None and group.font(0) == heading.font()
        assert group.foreground(0).color() == heading.palette().color(QPalette.ColorRole.WindowText)
        assert tree.font() == window.inspector.smoothing_label.font()
        assert window.library.empty_label.palette().color(
            QPalette.ColorRole.WindowText,
        ) == window.inspector.availability.palette().color(QPalette.ColorRole.WindowText)
        assert window.data is archived
        window.library.panel.grab().save(f".tmp/library-panel-{appearance.value}.png")
    window.set_appearance(APPEARANCE_CHOICES.index(Appearance.DARK))

    # The other export format is the same entry and does not reload the workspace.
    paths[:] = [str(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.zforces")))]
    window.choose_file(new_window=True)
    wait_until(window.open_action.isEnabled)
    assert len(store.entries()) == 1
    day = tree.topLevelItem(0)
    assert day is not None and day.childCount() == 1
    assert window.data is archived
    # A changed source UUID export updates and reloads the selected recording.
    updated_path = export_directory / "updated.forces"
    payload = json.loads(archived.source.recording.source.original_bytes)
    payload["name"] = "Manta updated"
    updated_path.write_text(json.dumps(payload), encoding="utf-8")
    paths[:] = [str(updated_path)]
    window.open_action.trigger()
    wait_until(window.open_action.isEnabled)
    wait_until(
        lambda: (
            window.data is not None
            and window.data.source.recording.metadata.name == "Manta updated"
        ),
    )
    assert len(store.entries()) == 1
    archived = window.data
    assert archived is not None
    selected = window.library.selected_entry
    assert selected is not None and selected.source_sha256 == archived.source.source_sha256
    assert selected.workflow_status == "markers_verified"
    assert "Ride: Manta updated" in " ".join(window.library.details.toPlainText().split())

    # Editing has its own dialog; the Library and workspace keep their dimensions.
    QApplication.processEvents()
    editor = window.library.editor
    panel_width = window.library.panel.width()
    window_size = window.size()
    digest = archived.source.source_sha256
    original_source = archived.source.recording
    window.library.edit_action.trigger()
    assert editor.isVisible() and editor.isWindow()
    assert editor.windowModality() == Qt.WindowModality.WindowModal
    assert [group.title() for group in editor.findChildren(QGroupBox)] == [
        "Recording details",
        "Notes",
    ]
    assert editor.windowTitle() == "Edit metadata…"
    assert window.library.panel.width() == panel_width and window.size() == window_size
    assert editor.fields["row"].placeholderText() == "3"
    for key, value in {
        "ride_name": "Edited ride",
        "park_name": "Edited park",
        "row": "Front",
        "seat": "Left",
        "train": "Blue",
    }.items():
        editor.fields[key].setText(value)
    editor.position.setCurrentIndex(editor.position.findData("Seated"))
    editor.notes.setPlainText("Library notes")
    QApplication.processEvents()
    editor.grab().save(".tmp/lib06-metadata-dialog.png")
    save = editor.buttons.button(QDialogButtonBox.StandardButton.Save)
    assert save.text().replace("&", "") == "Save" and not save.icon().isNull()
    notes_group = editor.notes.parentWidget()
    assert notes_group is not None and editor.buttons.y() > notes_group.y()
    save.click()
    wait_until(lambda: window.data is not None and window.data.title == "Edited ride")
    assert not editor.isVisible() and window.open_action.isEnabled()
    assert window.data is not None
    assert window.data.source.recording.metadata == original_source.metadata
    assert (
        window.data.source.recording.source.original_bytes == original_source.source.original_bytes
    )
    assert window.data.source.source_sha256 == digest
    assert "Edited ride" in window.heading.text() and "Edited park" in window.heading.text()
    assert dict(window.data.metadata_fields)["Row"] == "Front"
    assert "Ride: Manta updated" in " ".join(window.library.details.toPlainText().split())
    assert "Row: 3" in " ".join(window.library.details.toPlainText().split())
    assert window.library.park_filter.findData("Edited park") >= 0
    window.library.edit_action.trigger()
    assert editor.fields["ride_name"].text() == "Edited ride"
    assert editor.notes.toPlainText() == "Library notes"
    editor.fields["ride_name"].setText("Cancelled")
    cancel = editor.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    cancel.click()
    assert window.data.title == "Edited ride"
    stored = store.metadata(digest)
    assert stored is not None and stored.ride_name == "Edited ride"
    window.library.edit_action.trigger()
    editor.notes.setPlainText("Rejected")
    with store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_metadata BEFORE UPDATE ON recordings "
            "WHEN NEW.notes='Rejected' BEGIN SELECT RAISE(ABORT, 'injected metadata failure'); END",
        )
    save.click()
    assert editor.isVisible() and editor.error.isVisible()
    assert "Could not save Library metadata" in editor.error.text()
    assert store.metadata(digest) == stored
    assert window.data.title == "Edited ride"
    with store.connection() as connection:
        connection.execute("DROP TRIGGER reject_metadata")
    cancel.click()
    window.library.edit_action.trigger()
    assert editor.fields["ride_name"].text() == "Edited ride"
    for language, title in (
        (1, "Metadaten bearbeiten…"),
        (2, "Modifier les métadonnées…"),
        (0, "Edit metadata…"),
    ):
        window.set_ui_language(language)
        assert editor.windowTitle() == title
        assert editor.position.currentData() == "Seated"
    for appearance in (Appearance.LIGHT, Appearance.MANTA, Appearance.DARK):
        window.set_appearance(APPEARANCE_CHOICES.index(appearance))
        QApplication.processEvents()
        assert editor.fields["ride_name"].palette().color(
            QPalette.ColorRole.Text,
        ) == window.inspector.smoothing_label.palette().color(QPalette.ColorRole.WindowText)
        assert editor.position.currentData() == "Seated"
        if appearance is Appearance.LIGHT:
            editor.grab().save(".tmp/lib06-metadata-dialog-light.png")
    reset = editor.buttons.button(QDialogButtonBox.StandardButton.Reset)
    reset.click()
    wait_until(lambda: window.data is not None and window.data.title == "Manta updated")
    assert not editor.isVisible()
    archived = window.data
    assert archived is not None and archived.source.additions.notes == ""
    assert dict(archived.metadata_fields)["Row"] == "3"
    assert (
        archived.source.effective_metadata.riding_position
        == original_source.metadata.riding_position
    )

    # Unknown dates come last; full names remain available without widening the window.
    long_name = "LongRideName" * 100
    long_park = "LongParkName" * 100
    unknown_source = synthetic_source(name=long_name, location=long_park)
    unknown_path = export_directory / "unknown.forces"
    unknown_path.write_bytes(unknown_source.recording.source.original_bytes)
    paths[:] = [str(unknown_path)]
    QApplication.processEvents()
    wait_until(lambda: window.library.panel.width() > 0)
    window.library.panel.grab().save(".tmp/library-panel-preview.png")
    window_size = window.size()
    panel_width = window.library.panel.width()
    window.choose_file(new_window=True)
    wait_until(window.open_action.isEnabled)
    assert window.data is archived
    assert tree.topLevelItemCount() == 2
    unknown_day = tree.topLevelItem(1)
    assert unknown_day is not None and unknown_day.text(0) == "Unknown date"
    unknown_item = unknown_day.child(0)
    assert unknown_item is not None
    assert long_name in unknown_item.toolTip(0) and long_park in unknown_item.toolTip(0)
    assert tree.textElideMode() == Qt.TextElideMode.ElideRight
    tree.setCurrentItem(unknown_item)
    wait_until(window.open_action.isEnabled)
    assert (
        window.data is not None and window.data.source.source_sha256 == unknown_source.source_sha256
    )
    assert window.size() == window_size and window.library.panel.width() == panel_width
    assert "Recording time: Unknown date" in " ".join(window.library.details.toPlainText().split())
    assert "Riding position:" not in " ".join(window.library.details.toPlainText().split())

    # A failed archived selection leaves the existing chart/selection intact.
    manta_day = tree.topLevelItem(0)
    assert manta_day is not None
    manta_item = manta_day.child(0)
    assert manta_item is not None
    tree.setCurrentItem(manta_item)
    wait_until(window.open_action.isEnabled)
    retained = window.data
    window.plot.axis_x.setRange(60, 100)
    window.navigation.position.setValue(4000)
    window.inspector.first.setValue(3000)
    window.inspector.last.setValue(6000)
    with store.connection() as connection:
        connection.execute(
            "UPDATE recordings SET source_bytes=? WHERE source_sha256=?",
            (b"x" * unknown_source.byte_count, unknown_source.source_sha256),
        )
    tree.setCurrentItem(unknown_item)
    wait_until(window.open_action.isEnabled)
    assert window.data is retained
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == pytest.approx((60, 100))
    assert window.navigation.position.value() == 4000
    assert (window.inspector.first.value(), window.inspector.last.value()) == (3000, 6000)
    assert "integrity" in " ".join(window.library.details.toPlainText().split())
    assert "Could not open archived recording" in window.statusBar().currentMessage()
    assert not window.library.edit_action.isEnabled()
    window.library.toggle_button.click()
    QApplication.processEvents()
    assert window.workspace.width() == workspace_width
    wait_until(lambda: window.minimumSizeHint() == minimum)
    window.library.toggle_button.click()
    assert window.data is retained
    selected = window.library.selected_entry
    assert selected is not None and selected.source_sha256 == unknown_source.source_sha256

    # Filters read metadata without opening a recording or changing the chart.
    parks = window.library.park_filter
    search = window.library.search
    QApplication.processEvents()
    filter_position = parks.pos()
    search_position = search.pos()
    # Unknown parks initially have no results; the controls must stay at the top.
    parks.setCurrentIndex(parks.findData(""))
    QApplication.processEvents()
    assert tree.topLevelItemCount() == 0 and window.library.empty_label.isVisible()
    assert tree.isVisible() and window.library.empty_label.y() < tree.y()
    assert parks.pos() == filter_position
    assert search.pos() == search_position
    window.library.clear_filters.click()
    no_park = export_directory / "no-park.forces"
    no_park.write_bytes(synthetic_source(name="No park ride").recording.source.original_bytes)
    assert LibraryArchive(store).import_paths((no_park,))[0].status == "imported"
    window.library.refresh()
    choices = [parks.itemData(index) for index in range(parks.count())]
    assert choices[:2] == [None, ""]
    assert "Seaworld Orlando" in choices and long_park in choices
    resets = QSignalSpy(parks.model().modelReset)
    native_show = QComboBox.showPopup
    animation_states: list[bool] = []

    def observe_popup(combo: QComboBox) -> None:
        animation_states.append(QApplication.isEffectEnabled(Qt.UIEffect.UI_AnimateCombo))
        native_show(combo)

    effect = Qt.UIEffect.UI_AnimateCombo
    previous = QApplication.isEffectEnabled(effect)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(QComboBox, "showPopup", observe_popup)
            for enabled in (False, True):
                QApplication.setEffectEnabled(effect, enabled)
                parks.showPopup()
                assert parks.view().isVisible()
                assert QApplication.isEffectEnabled(effect) == enabled
                parks.hidePopup()
        assert animation_states == [False, False]
    finally:
        QApplication.setEffectEnabled(effect, previous)
    parks.showPopup()
    wait_until(parks.view().isVisible)
    parks.setCurrentIndex(1)
    QApplication.processEvents()
    assert parks.currentData() == ""
    assert resets.count() == 0
    assert parks.view().isVisible()
    parks.hidePopup()
    parks.setCurrentIndex(parks.findData("Seaworld Orlando"))
    search.setText("MANTA orlando")
    assert tree.topLevelItemCount() == 1
    group = tree.topLevelItem(0)
    assert group is not None and group.childCount() == 1
    assert [parks.itemData(index) for index in range(parks.count())] == choices
    search.setText("missing")
    assert tree.topLevelItemCount() == 0
    assert window.library.empty_label.isVisible()
    assert window.library.empty_label.text() == "No matching recordings"
    for language, caption, empty in (
        (1, "Alle Parks", "Keine passenden Aufnahmen"),
        (2, "Tous les parcs", "Aucun enregistrement correspondant"),
        (0, "All parks", "No matching recordings"),
    ):
        window.set_ui_language(language)
        assert parks.itemText(0) == caption
        assert window.library.empty_label.text() == empty
        assert parks.currentData() == "Seaworld Orlando" and search.text() == "missing"
    search.clear()
    assert tree.topLevelItemCount() == 1
    parks.setCurrentIndex(parks.findData(""))
    search.setText("no park")
    group = tree.topLevelItem(0)
    assert group is not None and group.text(0) == "Unknown date" and group.childCount() == 1
    window.library.toggle_button.click()
    window.library.toggle_button.click()
    assert parks.currentData() == "" and search.text() == "no park"
    assert tree.topLevelItemCount() == 1
    window.library.clear_filters.click()
    assert parks.currentData() is None and search.text() == ""
    assert not window.library.clear_filters.isEnabled()
    assert tree.topLevelItemCount() == 2
    group = tree.topLevelItem(1)
    assert group is not None and group.childCount() == 2
    assert window.data is retained and window.open_action.isEnabled()
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == pytest.approx((60, 100))
    assert window.navigation.position.value() == 4000
    assert resets.count() == 0

    # Status clicks address their own entry even when a different source is selected.
    selected_item = tree.currentItem()
    group = tree.topLevelItem(1)
    assert group is not None
    other_item = None
    for index in range(group.childCount()):
        candidate = group.child(index)
        if candidate is not None and candidate.text(0).splitlines()[0] == "No park ride":
            other_item = candidate
            break
    assert other_item is not None
    other_icon = tree.itemWidget(other_item, 1)
    assert isinstance(other_icon, WorkflowIcon)
    QTest.mouseClick(other_icon.button, Qt.MouseButton.LeftButton)
    selector = window.library.workflow_selector
    assert selector is not None
    QTest.mouseClick(selector.buttons["completed"], Qt.MouseButton.LeftButton)
    assert window.library.workflow_selector is None
    other_digest = other_item.data(0, Qt.ItemDataRole.UserRole)
    assert isinstance(other_digest, str)
    assert (
        next(
            entry for entry in store.entries() if entry.source_sha256 == other_digest
        ).workflow_status
        == "completed"
    )
    assert tree.currentItem() is selected_item and window.data is retained
    assert LibraryArchive(store).import_paths((no_park,))[0].status == "duplicate"
    store.update_metadata(other_digest, {"notes": "Current metadata"})
    assert (
        next(
            entry for entry in store.entries() if entry.source_sha256 == other_digest
        ).workflow_status
        == "completed"
    )


def test_workflow_filter_combines_filters_without_loading_or_changing_status(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    library = window.library
    store = LibraryStore()
    sources = (
        synthetic_source(name="Alpha ride", location="Park A", date=1000),
        synthetic_source(name="Alpha second", location="Park B", date=1001),
        synthetic_source(name="Other ride", location="Park A", date=1002),
        synthetic_source(name="Alpha completed", location="Park A", date=1003),
    )
    for source, status in zip(
        sources,
        ("markers_verified", "markers_verified", "imported", "completed"),
        strict=True,
    ):
        store.archive(source, "ride.forces", (2, 6), CalibrationOverrides())
        store.set_workflow_status(source.source_sha256, status)
    library.refresh()
    window.open_archived(sources[0].source_sha256)
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    library.toggle_button.click()
    window.navigation.position.setValue(4)
    window.inspector.first.setValue(3)
    window.inspector.last.setValue(5)
    retained = window.data
    before = store.entries()
    opened = QSignalSpy(library.open_requested)
    changed = QSignalSpy(library.changed)
    workflow = library.workflow_filter
    parks = library.park_filter
    assert [workflow.itemData(i) for i in range(workflow.count())] == [None, *WORKFLOW_STATUSES]

    def names() -> list[str]:
        result: list[str] = []
        for index in range(library.recordings.topLevelItemCount()):
            group = library.recordings.topLevelItem(index)
            assert group is not None
            for child_index in range(group.childCount()):
                item = group.child(child_index)
                assert item is not None
                result.append(item.text(0).splitlines()[0])
        return result

    assert len(names()) == 4
    workflow.setCurrentIndex(workflow.findData("markers_verified"))
    assert names() == ["Alpha second", "Alpha ride"]
    parks.setCurrentIndex(parks.findData("Park A"))
    library.search.setText("alpha")
    assert names() == ["Alpha ride"]
    for language in (1, 2, 0):
        window.set_ui_language(language)
        assert workflow.itemText(0) == tr("All statuses")
        assert workflow.currentText() == tr("Markers verified")
        assert workflow.currentData() == "markers_verified"
        assert parks.currentData() == "Park A" and library.search.text() == "alpha"
        assert names() == ["Alpha ride"]
    library.toggle_button.click()
    library.toggle_button.click()
    assert workflow.currentData() == "markers_verified" and names() == ["Alpha ride"]
    workflow.showPopup()
    wait_until(workflow.view().isVisible)
    workflow.hidePopup()
    workflow.setCurrentIndex(workflow.findData("uploaded"))
    assert names() == [] and library.empty_label.isVisible()
    assert library.empty_label.text() == "No matching recordings"
    assert library.clear_filters.isEnabled()
    workflow.setCurrentIndex(0)
    assert names() == ["Alpha completed", "Alpha ride"]
    library.clear_filters.click()
    assert workflow.currentData() is None and parks.currentData() is None
    assert not library.search.text() and len(names()) == 4
    assert not library.clear_filters.isEnabled()
    assert store.entries() == before and changed.count() == 0

    # A manual status change removes a row that no longer matches, without reloading the chart.
    parks.setCurrentIndex(parks.findData("Park A"))
    library.search.setText("alpha")
    workflow.setCurrentIndex(workflow.findData("markers_verified"))
    group = library.recordings.topLevelItem(0)
    assert group is not None
    item = group.child(0)
    assert item is not None
    icon = library.recordings.itemWidget(item, 1)
    assert isinstance(icon, WorkflowIcon)
    QTest.mouseClick(icon.button, Qt.MouseButton.LeftButton)
    selector = library.workflow_selector
    assert selector is not None
    QTest.mouseClick(selector.buttons["completed"], Qt.MouseButton.LeftButton)
    assert names() == [] and library.empty_label.isVisible()
    assert library.workflow_selector is None and changed.count() == 1
    assert store.entries(workflow_status="markers_verified")[0].ride_name == "Alpha second"
    assert window.data is retained and opened.count() == 0
    assert window.navigation.position.value() == 4
    assert (window.inspector.first.value(), window.inspector.last.value()) == (3, 5)
