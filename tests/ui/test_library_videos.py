"""Recording-specific video links and draft label options share existing dialog conventions."""

# cspell:words Videolinks

from PySide6.QtWidgets import QDialogButtonBox, QToolButton, QTreeWidgetItem
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPalette
import pytest
from PySide6.QtTest import QTest

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.explorer.library_workflow import LibraryIcon, WorkflowIcon
from ride_forces_analyzer.ui.presentation.icons import link_icon as make_link_icon
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.storage.preferences import Preferences, DEFAULT_LIBRARY_VIDEO_LABELS
from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from ride_forces_analyzer.ui.explorer.library_videos import LibraryVideosDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until


def test_library_video_dialog_and_settings_save_cancel(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert tree.columnCount() == 2
    opened_urls: list[str] = []
    browser_success = True

    def open_url(url: QUrl) -> bool:
        opened_urls.append(url.toString())
        return browser_success

    monkeypatch.setattr(QDesktopServices, "openUrl", open_url)

    def link_icon(digest: str) -> LibraryIcon | None:
        for index in range(tree.topLevelItemCount()):
            group = tree.topLevelItem(index)
            assert group is not None
            for child in range(group.childCount()):
                item = group.child(child)
                assert item is not None
                if item.data(0, Qt.ItemDataRole.UserRole) == digest:
                    icon = tree.itemWidget(item, 1)
                    assert isinstance(icon, WorkflowIcon)
                    layout = icon.layout()
                    assert layout is not None
                    layout.activate()
                    assert icon.links_icon.mapTo(icon, icon.links_icon.rect().center()).y() < (
                        icon.button.mapTo(icon, icon.button.rect().center()).y()
                    )
                    return icon.links_icon
        return None

    assert not window.library.videos_action.icon().isNull()

    def open_links() -> LibraryVideosDialog:
        window.library.videos_action.trigger()
        dialog = window.findChild(LibraryVideosDialog)
        assert dialog is not None and dialog.isVisible()
        return dialog

    def saved_item(dialog: LibraryVideosDialog, index: int) -> QTreeWidgetItem:
        item = dialog.links.topLevelItem(index)
        assert item is not None
        return item

    def browser_button(dialog: LibraryVideosDialog, index: int = 0) -> QToolButton:
        icon = dialog.links.itemWidget(saved_item(dialog, index), 1)
        assert isinstance(icon, LibraryIcon)
        return icon.button

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
    assert dialog.error.isVisible() and dialog.links.topLevelItemCount() == 0
    dialog.url.setText("https://example.invalid/private?scheduled=1")
    dialog.label.setCurrentText("YouTube")
    assert opened_urls == []
    assert store.video_links(digest) == ()
    save.click()
    assert dialog.links.topLevelItemCount() == 1
    icon = link_icon(digest)
    assert icon is not None and not icon.button.icon().isNull()

    def assert_link_color(digest: str, role: QPalette.ColorRole) -> None:
        icon = link_icon(digest)
        assert icon is not None and icon.button.isEnabled()
        expected = make_link_icon(tree.palette().color(role))
        assert icon.button.icon().pixmap(20, 20).toImage() == expected.pixmap(20, 20).toImage()

    assert_link_color(digest, QPalette.ColorRole.HighlightedText)
    assert_link_color(sources[1].source_sha256, QPalette.ColorRole.PlaceholderText)

    dialog.add.click()
    dialog.url.setText("https://example.invalid/short")
    dialog.label.setCurrentText("Shorts")
    save.click()
    assert dialog.links.topLevelItemCount() == 2
    dialog.links.setCurrentItem(saved_item(dialog, 0))
    dialog.url.setText("https://example.invalid/edited")
    save.click()
    assert store.video_links(digest)[0].url.endswith("/edited")
    dialog.url.setText("https://example.invalid/unsaved")
    browser_button(dialog, 1).click()
    assert opened_urls[-1] == "https://example.invalid/short"
    assert dialog.url.text() == "https://example.invalid/unsaved"
    assert dialog.links.currentItem() is dialog.links.topLevelItem(0)
    browser_success = False
    browser_button(dialog).click()
    assert opened_urls[-1] == "https://example.invalid/edited"
    assert dialog.error.isVisible()
    assert dialog.error.text() == "Could not open the video link in your browser."
    assert store.video_links(digest)[0].url.endswith("/edited")
    browser_success = True
    browser_button(dialog).click()
    assert not dialog.error.isVisible()
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
    dialog.links.setCurrentItem(saved_item(dialog, 0))
    assert dialog.label.currentData() == "YouTube"
    assert dialog.label.findData("Private") >= 0
    assert dialog.label.findData("Shorts") == -1
    dialog.links.setCurrentItem(saved_item(dialog, 1))
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
    dialog.links.setCurrentItem(saved_item(dialog, 0))
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
    dialog.links.setCurrentItem(saved_item(dialog, 0))
    assert dialog.label.currentData() == "YouTube"
    assert dialog.label.count() == 2
    assert dialog.windowTitle() == "Videolinks…"
    assert_link_color(digest, QPalette.ColorRole.HighlightedText)
    assert_link_color(sources[1].source_sha256, QPalette.ColorRole.PlaceholderText)
    assert browser_button(dialog).toolTip() == tr("Open in browser")
    assert not browser_button(dialog).icon().isNull()
    dialog.grab().save(".tmp/lib09-videos-light.png")
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    wait_until(lambda: window.findChild(LibraryVideosDialog) is None)
    assert store.video_links(sources[1].source_sha256) == ()
    assert (
        next(entry for entry in store.entries() if entry.source_sha256 == digest).workflow_status
        == "uploaded"
    )
    assert window.data is data

    # The indicator addresses its own recording, leaving the selected ride open.
    other_digest = sources[1].source_sha256
    store.save_video_link(other_digest, "https://example.invalid/second")
    window.library.refresh()
    current = window.library.selected_entry
    assert current is not None and current.source_sha256 == digest
    assert_link_color(other_digest, QPalette.ColorRole.Highlight)
    other_icon = link_icon(other_digest)
    assert other_icon is not None
    QTest.mouseClick(other_icon.button, Qt.MouseButton.LeftButton)
    dialog = window.findChild(LibraryVideosDialog)
    assert dialog is not None and dialog.source_sha256 == other_digest
    assert window.data is data and window.library.selected_entry == current
    dialog.links.setCurrentItem(saved_item(dialog, 0))
    browser_button(dialog).click()
    assert opened_urls[-1] == "https://example.invalid/second"
    dialog.remove.click()
    assert_link_color(other_digest, QPalette.ColorRole.PlaceholderText)
    assert store.video_links(other_digest) == ()
    close_links(dialog)
    assert window.data is data

    # An empty link action stays usable for adding the first link.
    empty_icon = link_icon(other_digest)
    assert empty_icon is not None
    empty_icon.button.click()
    dialog = window.findChild(LibraryVideosDialog)
    assert dialog is not None and dialog.source_sha256 == other_digest
    assert dialog.links.topLevelItemCount() == 0
    close_links(dialog)
