"""Optional background checks and update actions without network or browser launch."""

from PySide6.QtCore import QEvent, QUrl
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
import pytest

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.ui import updates as ui_updates
from ride_forces_analyzer.ui.about import AboutDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from ride_forces_analyzer.updates import AvailableRelease, REPOSITORY_URL
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
    assert about is not None and not about.automatic_updates.isChecked()
    about.check_updates.click()
    wait_until(lambda: window.updates.worker is None)
    notice = window.findChild(QMessageBox, "updateNotice")
    assert notice is not None and notice.isVisible()
    assert "v0.3.1" in notice.text()
    button(notice, "Later").click()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.preferences.skipped_update() == ""
    about.check_updates.click()
    wait_until(lambda: window.updates.worker is None)
    notice = window.findChild(QMessageBox, "updateNotice")
    assert notice is not None
    button(notice, "Skip this version").click()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.preferences.skipped_update() == "v0.3.1"
    about.automatic_updates.setChecked(True)
    window.preferences.remember_update_check(0)
    window.updates.check(manual=False)
    wait_until(lambda: window.updates.worker is None)
    assert window.findChild(QMessageBox, "updateNotice") is None
    opened: list[str] = []

    def open_url(url: QUrl) -> bool:
        opened.append(url.toString())
        return True

    monkeypatch.setattr(ui_updates.QDesktopServices, "openUrl", open_url)
    about.check_updates.click()  # A manual check deliberately ignores the skipped version.
    wait_until(lambda: window.updates.worker is None)
    notice = window.findChild(QMessageBox, "updateNotice")
    assert notice is not None
    button(notice, "Open release").click()
    assert opened == [candidate.url]
    about.close()


def test_opted_in_startup_checks_once_then_remains_quiet_for_the_day(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.config import AppSettings

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
    window.about_action.trigger()
    about = window.findChild(AboutDialog)
    assert about is not None
    about.check_updates.click()
    wait_until(lambda: window.updates.worker is None)
    assert "unavailable" in about.update_status.text()
    assert about.check_updates.isEnabled()
    about.close()
