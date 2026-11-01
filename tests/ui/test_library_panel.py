"""Native Library interactions, explicit archive import and preserved chart state."""

# cspell:words Seaworld Uhrzeit Heure Importiert Importé Keine passenden Aufnahmen Tous Aucun enregistrement correspondant

from pathlib import Path
import json

from PySide6.QtWidgets import QApplication, QComboBox, QFileDialog, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QSignalSpy
import pytest

from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.storage.preferences import Appearance
from ride_forces_analyzer.ui.dialogs.settings import APPEARANCE_CHOICES
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import resize_workspace, wait_until
from tests.analysis.test_recording_preparation import synthetic_source


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

    # Ordinary opening does not archive; only the Library's explicit import does.
    store = LibraryStore()
    with store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM recordings").fetchone() == (0,)
    resize_workspace(window, 1920, 1040)
    window.library.toggle_button.click()
    bad = export_directory / "bad.forces"
    bad.write_bytes(b"invalid JSON")
    paths = [str(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))), str(bad)]

    def choose(*args: object, **kwargs: object) -> tuple[list[str], str]:
        return paths, ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", choose)
    window.library.import_button.click()
    wait_until(window.library.import_button.isEnabled)
    report = window.library.import_results.toPlainText()
    assert "Imported" in report and "bad.forces: Import failed:" in report
    assert window.library.import_results.isVisible()
    with store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM recordings").fetchone() == (1,)
    paths[:] = paths[:1]
    window.library.import_button.click()
    wait_until(window.library.import_button.isEnabled)
    assert "Already in Library" in window.library.import_results.toPlainText()
    paths.clear()
    window.library.import_button.click()
    assert window.library.import_button.isEnabled()
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
    assert item.toolTip(1) == "Imported" and not item.icon(1).isNull()
    tree.setCurrentItem(item)
    assert not tree.isEnabled()
    wait_until(window.open_action.isEnabled)
    assert tree.isEnabled() and window.data is not None and window.data is not data
    assert window.data.source.recording.source.provenance.path is None
    assert window.library.details.isReadOnly()
    details = window.library.details.toPlainText()
    assert "2026-09-17 10:17:41 (America/New_York)" in details
    assert "Import time (UTC):" in details and "Row: 3" in details
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
    assert not current_item.icon(1).isNull() and window.data is archived
    for appearance in (Appearance.DARK, Appearance.LIGHT, Appearance.MANTA):
        window.set_appearance(APPEARANCE_CHOICES.index(appearance))
        QApplication.processEvents()
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
    window.library.import_button.click()
    wait_until(window.library.import_button.isEnabled)
    assert "Already in Library" in window.library.import_results.toPlainText()
    day = tree.topLevelItem(0)
    assert day is not None and day.childCount() == 1
    assert window.data is archived
    # A changed source UUID export updates and reloads the selected recording.
    updated_path = export_directory / "updated.forces"
    payload = json.loads(archived.source.recording.source.original_bytes)
    payload["name"] = "Manta updated"
    updated_path.write_text(json.dumps(payload), encoding="utf-8")
    paths[:] = [str(updated_path)]
    window.library.import_button.click()
    wait_until(window.library.import_button.isEnabled)
    wait_until(
        lambda: (
            window.data is not None
            and window.data.source.recording.metadata.name == "Manta updated"
        ),
    )
    assert "Updated in Library" in window.library.import_results.toPlainText()
    assert len(store.entries()) == 1
    archived = window.data
    assert archived is not None
    selected = window.library.selected_entry
    assert selected is not None and selected.source_sha256 == archived.source.source_sha256
    assert selected.workflow_status == "markers_verified"
    assert "Ride: Manta updated" in window.library.details.toPlainText()

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
    window.library.import_button.click()
    wait_until(window.library.import_button.isEnabled)
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
    assert "Recording time: Unknown date" in window.library.details.toPlainText()
    assert "Riding position:" not in window.library.details.toPlainText()

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
    assert "integrity" in window.library.details.toPlainText()
    assert "Could not open archived recording" in window.statusBar().currentMessage()
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
