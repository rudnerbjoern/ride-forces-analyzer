"""Library context actions target the clicked recording and reuse the existing dialogs."""

# cspell:words Metadaten bearbeiten Videolinks Exportverlauf métadonnées Liens vidéo Historique exports
# cspell:words Entfernen Supprimer
# cspell:words neuem Fenster öffnen Ouvrir dans une nouvelle fenêtre

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.ui.explorer.library_exports import LibraryExportsDialog
from ride_forces_analyzer.ui.explorer.library_videos import LibraryVideosDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until


def test_recording_context_menu_targets_rows_and_opens_dialogs(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    library = window.library
    sources = (synthetic_source(name="First ride"), synthetic_source(name="Second ride"))
    store = LibraryStore()
    for source in sources:
        store.archive(source, "ride.forces", (2, 6), CalibrationOverrides())
    library.toggle_button.click()
    tree = library.recordings
    group = tree.topLevelItem(0)
    assert group is not None
    first, second = group.child(0), group.child(1)
    assert first is not None and second is not None
    tree.setCurrentItem(first)
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    assert not any(
        button.text() in {"Metadata…", "Video links…", "Export history…"}
        for button in library.panel.findChildren(QPushButton)
    )

    def right_click(position: QPoint) -> None:
        QTest.mouseClick(tree.viewport(), Qt.MouseButton.RightButton, pos=position)
        # QTest sends mouse events; the platform's separate context event follows them.
        assert tree.isEnabled()
        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            position,
            tree.viewport().mapToGlobal(position),
        )
        QApplication.sendEvent(tree.viewport(), event)
        QApplication.processEvents()

    menu = library.context_menu
    right_click(tree.visualItemRect(group).center())
    assert not menu.isVisible() and tree.currentItem() is first
    right_click(QPoint(10, tree.viewport().height() - 5))
    assert not menu.isVisible() and tree.currentItem() is first
    assert window.data is data

    right_click(tree.visualItemRect(second).center())
    assert menu.isVisible() and tree.currentItem() is second
    wait_until(window.open_action.isEnabled)
    entry = library.selected_entry
    assert entry is not None
    digest = second.data(0, Qt.ItemDataRole.UserRole)
    assert entry.source_sha256 == digest
    assert window.data is not None and window.data.source.source_sha256 == digest
    actions = [action for action in menu.actions() if not action.isSeparator()]
    assert actions == [
        library.new_window_action,
        library.edit_action,
        library.videos_action,
        library.history_action,
        library.remove_action,
    ]
    assert menu.actions()[-2].isSeparator()
    assert all(action.isEnabled() and not action.icon().isNull() for action in actions)
    size = window.size()
    panel_width = library.panel.width()

    requests = QSignalSpy(window.archive_window_requested)
    retained = window.data
    QTest.mouseClick(
        menu,
        Qt.MouseButton.LeftButton,
        pos=menu.actionGeometry(library.new_window_action).center(),
    )
    assert requests.count() == 1 and requests.at(0) == [digest]
    assert window.data is retained and not menu.isVisible()
    right_click(tree.visualItemRect(second).center())
    QTest.mouseClick(
        menu,
        Qt.MouseButton.LeftButton,
        pos=menu.actionGeometry(library.edit_action).center(),
    )
    assert library.editor.isVisible() and not menu.isVisible()
    assert library.editor.fields["ride_name"].placeholderText() == entry.ride_name
    library.editor.reject()
    assert window.size() == size and library.panel.width() == panel_width

    right_click(tree.visualItemRect(second).center())
    QTest.mouseClick(
        menu,
        Qt.MouseButton.LeftButton,
        pos=menu.actionGeometry(library.videos_action).center(),
    )
    videos = window.findChild(LibraryVideosDialog)
    assert videos is not None and videos.isVisible() and videos.source_sha256 == digest
    videos.reject()
    wait_until(lambda: window.findChild(LibraryVideosDialog) is None)

    right_click(tree.visualItemRect(second).center())
    QTest.mouseClick(
        menu,
        Qt.MouseButton.LeftButton,
        pos=menu.actionGeometry(library.history_action).center(),
    )
    history = window.findChild(LibraryExportsDialog)
    assert history is not None and history.isVisible() and history.source_sha256 == digest
    history.reject()
    wait_until(lambda: window.findChild(LibraryExportsDialog) is None)
    second = tree.currentItem()
    assert second is not None

    retained = window.data
    for language, captions in (
        (
            0,
            ["Open in new window…", "Edit metadata…", "Video links…", "Export history…", "Remove…"],
        ),
        (
            1,
            [
                "In neuem Fenster öffnen …",
                "Metadaten bearbeiten…",
                "Videolinks…",
                "Exportverlauf…",
                "Entfernen…",
            ],
        ),
        (
            2,
            [
                "Ouvrir dans une nouvelle fenêtre…",
                "Modifier les métadonnées…",
                "Liens vidéo…",
                "Historique des exports…",
                "Supprimer…",
            ],
        ),
    ):
        window.set_ui_language(language)
        window.set_appearance(language % 2)
        right_click(tree.visualItemRect(second).center())
        assert menu.isVisible()
        assert [action.text() for action in actions] == captions
        QTest.keyClick(menu, Qt.Key.Key_Escape)
        assert not menu.isVisible()
        assert window.data is retained and tree.currentItem() is second

    window.set_ui_language(0)
    prompts: list[tuple[str, str, QMessageBox.StandardButton, bool, bool]] = []

    def remove(answer: QMessageBox.StandardButton) -> None:
        def respond() -> None:
            box = QApplication.activeModalWidget()
            assert isinstance(box, QMessageBox)
            prompts.append(
                (
                    box.windowTitle(),
                    box.text(),
                    box.standardButton(box.defaultButton()),
                    not box.button(QMessageBox.StandardButton.Yes).icon().isNull(),
                    not box.button(QMessageBox.StandardButton.No).icon().isNull(),
                ),
            )
            box.button(answer).click()

        right_click(tree.visualItemRect(second).center())
        QTimer.singleShot(0, respond)
        QTest.mouseClick(
            menu,
            Qt.MouseButton.LeftButton,
            pos=menu.actionGeometry(library.remove_action).center(),
        )

    before = store.entries()
    changes = QSignalSpy(library.changed)
    remove(QMessageBox.StandardButton.No)
    assert changes.count() == 0
    assert store.entries() == before and tree.currentItem() is second
    assert prompts[0][0] == "Remove recording?"
    assert f'Remove "{entry.ride_name}"' in prompts[0][1]
    assert "export history" in prompts[0][1] and "Original files" in prompts[0][1]
    assert prompts[0][2] == QMessageBox.StandardButton.No
    assert prompts[0][3:] == (True, True)

    with store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_removal BEFORE DELETE ON recordings "
            "BEGIN SELECT RAISE(ABORT, 'injected removal failure'); END",
        )
    remove(QMessageBox.StandardButton.Yes)
    assert changes.count() == 0
    assert store.entries() == before and tree.currentItem() is second
    assert "Could not remove recording" in library.details.toPlainText()
    assert window.data is retained
    with store.connection() as connection:
        connection.execute("DROP TRIGGER reject_removal")
    remove(QMessageBox.StandardButton.Yes)
    assert changes.count() == 1 and changes.at(0) == [library]
    assert [item.source_sha256 for item in store.entries()] == [
        source.source_sha256 for source in sources if source.source_sha256 != digest
    ]
    assert tree.currentItem() is None and library.selected_entry is None
    group = tree.topLevelItem(0)
    assert tree.topLevelItemCount() == 1 and group is not None and group.childCount() == 1
    assert not library.remove_action.isEnabled() and not library.details.isVisible()
    assert window.data is retained
