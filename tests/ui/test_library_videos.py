"""Recording-specific video links and draft label options share existing dialog conventions."""

# cspell:words Videolinks

from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.storage.preferences import Preferences, DEFAULT_LIBRARY_VIDEO_LABELS
from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from ride_forces_analyzer.ui.explorer.library_videos import LibraryVideosDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until


def test_library_video_dialog_and_settings_save_cancel(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    store = LibraryStore()
    sources = (synthetic_source(name="First ride"), synthetic_source(name="Second ride"))
    for source in sources:
        store.archive(source, "ride.forces", (2, 6), CalibrationOverrides())
    digest = sources[0].source_sha256
    store.set_workflow_status(digest, "uploaded")
    window.library.toggle_button.click()
    tree = window.library.recordings
    group = tree.topLevelItem(0)
    assert group is not None
    selected = None
    for index in range(group.childCount()):
        item = group.child(index)
        if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == digest:
            selected = item
    assert selected is not None
    tree.setCurrentItem(selected)
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    assert window.library.edit_button.size() == window.library.videos_button.size()
    assert not window.library.videos_button.icon().isNull()

    def open_links() -> LibraryVideosDialog:
        window.library.videos_button.click()
        dialog = window.findChild(LibraryVideosDialog)
        assert dialog is not None and dialog.isVisible()
        return dialog

    def close_links(dialog: LibraryVideosDialog) -> None:
        dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
        wait_until(lambda: window.findChild(LibraryVideosDialog) is None)

    dialog = open_links()
    assert not dialog.label.isEditable()
    assert tuple(dialog.label.itemData(i) for i in range(dialog.label.count())) == (
        "",
        *DEFAULT_LIBRARY_VIDEO_LABELS,
    )
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
    dialog.url.setText("file:///bad")
    save.click()
    assert dialog.error.isVisible() and dialog.links.count() == 0
    dialog.url.setText("https://example.invalid/private?scheduled=1")
    dialog.label.setCurrentText("YouTube")
    save.click()
    assert dialog.links.count() == 1
    dialog.add.click()
    dialog.url.setText("https://example.invalid/short")
    dialog.label.setCurrentText("Shorts")
    save.click()
    assert dialog.links.count() == 2
    dialog.links.setCurrentRow(0)
    dialog.url.setText("https://example.invalid/edited")
    save.click()
    assert store.video_links(digest)[0].url.endswith("/edited")
    dialog.url.setText("https://example.invalid/unsaved")
    window.grab().save(".tmp/lib09-library.png")
    dialog.grab().save(".tmp/lib09-videos-dark.png")
    close_links(dialog)
    assert store.video_links(digest)[0].url.endswith("/edited")

    def settings() -> SettingsDialog:
        window.settings_action.trigger()
        result = window.findChild(SettingsDialog, "settingsDialog")
        assert result is not None and result.isVisible()
        return result

    options = settings()
    editor = options.library_labels
    editor.choices.setCurrentRow(0)
    editor.name.setText("Renamed")
    editor.rename.click()
    editor.name.setText("Private")
    editor.add.click()
    options.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    wait_until(lambda: window.findChild(SettingsDialog) is None)
    assert Preferences().library_video_labels() == DEFAULT_LIBRARY_VIDEO_LABELS
    options = settings()
    editor = options.library_labels
    editor.choices.setCurrentRow(0)
    editor.name.setText("Renamed")
    editor.rename.click()
    editor.choices.setCurrentRow(1)
    editor.remove.click()
    editor.name.setText("Private")
    editor.add.click()
    options.grab().save(".tmp/lib10-settings-dark.png")
    expected = editor.labels()
    options.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    wait_until(lambda: window.findChild(SettingsDialog) is None)
    assert Preferences().library_video_labels() == expected
    dialog = open_links()
    dialog.links.setCurrentRow(0)
    assert dialog.label.currentData() == "YouTube"
    assert dialog.label.findData("Private") >= 0
    assert dialog.label.findData("Shorts") == -1
    dialog.links.setCurrentRow(1)
    assert dialog.label.currentData() == "Shorts"
    dialog.remove.click()
    assert len(store.video_links(digest)) == 1
    dialog.add.click()
    dialog.url.setText("http://example.invalid/unlabelled")
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
    save.click()
    assert store.video_links(digest)[1].label == ""
    with store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_ui_link BEFORE UPDATE ON video_links "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END",
        )
    dialog.links.setCurrentRow(0)
    dialog.url.setText("https://example.invalid/failure")
    save.click()
    assert dialog.error.isVisible() and dialog.url.text().endswith("/failure")
    assert store.video_links(digest)[0].url.endswith("/edited")
    close_links(dialog)
    options = settings()
    assert options.library_labels.labels() == expected
    options.library_labels.choices.clear()
    options.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    wait_until(lambda: window.findChild(SettingsDialog) is None)
    assert Preferences().library_video_labels() == ()
    window.set_ui_language(1)
    window.set_appearance(1)
    dialog = open_links()
    dialog.links.setCurrentRow(0)
    assert dialog.label.currentData() == "YouTube"
    assert dialog.label.count() == 2
    assert dialog.windowTitle() == "Videolinks…"
    dialog.grab().save(".tmp/lib09-videos-light.png")
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: window.findChild(LibraryVideosDialog) is None)
    assert store.video_links(sources[1].source_sha256) == ()
    assert (
        next(entry for entry in store.entries() if entry.source_sha256 == digest).workflow_status
        == "uploaded"
    )
    assert window.data is data
