"""About information remains accessible and follows the UI language."""

# cspell:words Über Unabhängiges Projekt Schließen Diagnoseinformationen kopieren Kopiert

from xml.etree.ElementTree import fromstring

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from ride_forces_analyzer import __version__
from ride_forces_analyzer.ui.about import AboutDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.ui.helpers import wait_until
import pytest


def test_about_dialog_identity_translation_and_reuse(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    window.about_action.trigger()
    dialog = window.findChild(AboutDialog, "aboutDialog")
    assert dialog is not None and dialog.isVisible()
    labels = dialog.findChildren(QLabel)
    text = "\n".join(label.text() for label in labels)
    for value in (__version__, "Björn Rudner", "GPL", "CC BY-SA 4.0", "not affiliated"):
        assert value in text
    assert any("not affiliated" in label.text() and "RFDB" in label.text() for label in labels)
    links = {
        anchor.get("href")
        for label in labels
        if label.openExternalLinks()
        for anchor in fromstring(f"<div>{label.text()}</div>").iter("a")
    }
    assert {"https://rideforces.com/", "https://rideforcesdb.com/"} <= links
    window.set_ui_language(1)
    window.set_appearance(1)
    QApplication.processEvents()
    assert dialog.windowTitle() == "Über Ride Forces Analyzer"
    assert any(
        "Unabhängiges Projekt" in label.text() and "RFDB" in label.text() for label in labels
    )
    window.about_action.trigger()
    assert len(window.findChildren(AboutDialog)) == 1
    close = next(
        button for button in dialog.findChildren(QPushButton) if button.text() == "Schließen"
    )
    assert close is not None and close.text() == "Schließen"
    scroll = dialog.findChild(QScrollArea)
    assert scroll is not None
    QApplication.processEvents()
    assert scroll.verticalScrollBar().maximum() == 0
    assert close.parentWidget() is dialog
    assert dialog.copy_diagnostics.parentWidget() is dialog
    close.click()
    assert not dialog.isVisible()


def test_copy_diagnostics_uses_worker_and_localized_feedback(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtCore import QThread
    from ride_forces_analyzer.ui import about

    application = QApplication.instance()
    assert application is not None

    def collect() -> str:
        assert QThread.currentThread() != application.thread()
        return "Ride Forces Analyzer: test\nFFmpeg: Not found"

    monkeypatch.setattr(about, "collect_diagnostics", collect)
    explorer_window.set_ui_language(1)
    explorer_window.about_action.trigger()
    dialog = explorer_window.findChild(AboutDialog, "aboutDialog")
    assert dialog is not None
    assert dialog.copy_diagnostics.text() == "Diagnoseinformationen kopieren"
    clipboard = QApplication.clipboard()
    previous = clipboard.text()
    try:
        dialog.copy_diagnostics.click()
        assert not dialog.copy_diagnostics.isEnabled()
        wait_until(lambda: dialog.diagnostic_worker is None)
        assert clipboard.text() == "Ride Forces Analyzer: test\nFFmpeg: Not found"
        assert dialog.copy_diagnostics.text() == "Kopiert"
        dialog.copy_reset.timeout.emit()
        assert dialog.copy_diagnostics.text() == "Diagnoseinformationen kopieren"
    finally:
        clipboard.setText(previous)
        dialog.close()
