"""Settings remains usable without native geometry warnings as content changes."""

from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea

from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.ui.helpers import wait_until


def test_settings_scrolls_with_persistent_actions_and_no_geometry_warning(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    messages: list[str] = []

    def message_handler(kind: QtMsgType, context: QMessageLogContext, message: str) -> None:
        if "setGeometry" in message and "settingsDialogWindow" in message:
            messages.append(message)
        if previous is not None:
            previous(kind, context, message)

    previous = qInstallMessageHandler(message_handler)
    try:
        window.settings_action.trigger()
        dialog = window.findChild(SettingsDialog, "settingsDialog")
        assert dialog is not None
        wait_until(lambda: dialog.windowHandle().isExposed())
        scroll = dialog.findChild(QScrollArea, "settingsContentScroll")
        assert scroll is not None
        assert dialog.frameGeometry().height() <= dialog.screen().availableGeometry().height()
        dialog.resize(540, 360)
        QTest.qWait(50)
        assert dialog.height() == 360
        assert scroll.verticalScrollBar().maximum() > 0
        assert dialog.rect().contains(dialog.buttons.geometry())
        for language in (1, 2, 0):
            window.set_ui_language(language)
            for appearance in (1, 2):
                window.set_appearance(appearance)
                dialog.library_transfer.status.emit("A long transfer failure explanation. " * 12)
                QTest.qWait(30)
                assert dialog.height() == 360
                assert dialog.buttons.isVisible()
                scroll.ensureWidgetVisible(dialog.library_transfer.restore_button)
                assert (
                    scroll.viewport()
                    .rect()
                    .intersects(
                        dialog.library_transfer.restore_button.rect().translated(
                            dialog.library_transfer.restore_button.mapTo(
                                scroll.viewport(),
                                dialog.library_transfer.restore_button.rect().topLeft(),
                            ),
                        ),
                    )
                )
        dialog.library_transfer.status.emit("")
        dialog.resize(540, min(1000, dialog.screen().availableGeometry().height() - 80))
        QTest.qWait(50)
        assert dialog.library_labels.height() <= dialog.library_labels.sizeHint().height()
        assert dialog.rect().contains(dialog.buttons.geometry())
        dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
        wait_until(lambda: window.findChild(SettingsDialog) is None)
        assert not messages
    finally:
        qInstallMessageHandler(previous)
