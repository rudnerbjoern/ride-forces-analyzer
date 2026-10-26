"""Optional background checks and update actions without network or browser launch."""

from PySide6.QtCore import QEvent, QUrl
from PySide6.QtWidgets import QApplication, QCheckBox, QDialogButtonBox, QMessageBox, QPushButton
from threading import Event
import pytest

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.ui.presentation import updates as ui_updates
from ride_forces_analyzer.ui.dialogs.about import AboutDialog
from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.runtime.updates import AvailableRelease, REPOSITORY_URL
from tests.ui.helpers import wait_until


def button(notice: QMessageBox, text: str) -> QPushButton:
    return next(item for item in notice.findChildren(QPushButton) if item.text() == text)


def test_manual_update_popup_skip_and_open_actions(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    candidate = AvailableRelease("v0.3.1", f"{REPOSITORY_URL}/releases/tag/v0.3.1")

    def available(current: str) -> AvailableRelease:
        return candidate

    monkeypatch.setattr(ui_updates, "check_for_update", available)
    window.about_action.trigger()
    about = window.findChild(AboutDialog)
    assert about is not None and not about.findChildren(QCheckBox)
    assert all(item.text() != "Check for updates…" for item in about.findChildren(QPushButton))
    window.settings_action.trigger()
    settings = window.findChild(SettingsDialog)
    assert settings is not None and settings.check_updates.isVisible()
    assert not settings.automatic_updates.isChecked()
    settings.check_updates.click()
    wait_until(lambda: window.updates.worker is None)
    notice = window.findChild(QMessageBox, "updateNotice")
    assert notice is not None and notice.isVisible()
    assert QApplication.activeModalWidget() is notice
    assert "v0.3.1" in notice.text()
    button(notice, "Later").click()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.preferences.skipped_update() == ""
    settings.check_updates.click()
    wait_until(lambda: window.updates.worker is None)
    notice = window.findChild(QMessageBox, "updateNotice")
    assert notice is not None
    button(notice, "Skip this version").click()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.preferences.skipped_update() == "v0.3.1"
    settings.automatic_updates.setChecked(True)
    settings.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.preferences.automatic_updates()
    window.preferences.remember_update_check(0)
    window.updates.check(manual=False)
    wait_until(lambda: window.updates.worker is None)
    assert window.findChild(QMessageBox, "updateNotice") is None
    opened: list[str] = []

    def open_url(url: QUrl) -> bool:
        opened.append(url.toString())
        return True

    monkeypatch.setattr(ui_updates.QDesktopServices, "openUrl", open_url)
    window.settings_action.trigger()
    settings = window.findChild(SettingsDialog)
    assert settings is not None and settings.automatic_updates.isChecked()
    settings.check_updates.click()  # A manual check deliberately ignores the skipped version.
    wait_until(lambda: window.updates.worker is None)
    notice = window.findChild(QMessageBox, "updateNotice")
    assert notice is not None
    button(notice, "Open release").click()
    assert opened == [candidate.url]
    settings.reject()
    about.close()


def test_opted_in_startup_checks_once_then_remains_quiet_for_the_day(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.runtime.config import AppSettings

    calls: list[str] = []

    def available(current: str) -> None:
        calls.append(current)

    monkeypatch.setattr(ui_updates, "check_for_update", available)
    preferences = explorer_window.preferences
    preferences.remember_automatic_updates(True)
    restored = ExplorerWindow(AppSettings(language=Language.ENGLISH))
    try:
        wait_until(lambda: len(calls) == 1 and restored.updates.worker is None)
        restored.updates.check(manual=False)
        QApplication.processEvents()
        assert len(calls) == 1
        assert restored.findChild(QMessageBox) is None
    finally:
        restored.close()
        restored.deleteLater()


def test_offline_automatic_check_is_silent_and_manual_check_explains_failure(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(current: str) -> None:
        raise OSError("offline")

    monkeypatch.setattr(ui_updates, "check_for_update", fail)
    window = explorer_window
    window.preferences.remember_automatic_updates(True)
    window.updates.check(manual=False)
    wait_until(lambda: window.updates.worker is None)
    assert window.findChild(QMessageBox) is None
    release = Event()

    def waiting_failure(current: str) -> None:
        if not release.wait(5):
            raise TimeoutError("Update worker was not released")
        raise OSError("offline")

    monkeypatch.setattr(ui_updates, "check_for_update", waiting_failure)
    window.settings_action.trigger()
    settings = window.findChild(SettingsDialog)
    assert settings is not None
    QApplication.processEvents()
    initial_size = settings.size()
    try:
        settings.check_updates.click()
        QApplication.processEvents()
        assert settings.size() == initial_size
        assert not settings.check_updates.isEnabled()
        assert "Checking" in settings.update_status.text()
        settings.reject()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        window.settings_action.trigger()
        settings = window.findChild(SettingsDialog)
        assert settings is not None and not settings.check_updates.isEnabled()
        QApplication.processEvents()
        initial_size = settings.size()
    finally:
        release.set()
    wait_until(lambda: window.updates.worker is None)
    assert "unavailable" in settings.update_status.text()
    assert settings.check_updates.isEnabled()
    QApplication.processEvents()
    assert settings.size() == initial_size
    settings.reject()
