"""About information remains accessible and follows the UI language."""

# cspell:words Über Unabhängiges Projekt Schließen

from xml.etree.ElementTree import fromstring

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from ride_forces_analyzer import __version__
from ride_forces_analyzer.ui.about import AboutDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from test_explorer_gui import explorer_window as explorer_window


def test_about_dialog_identity_translation_and_reuse(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    window.about_action.trigger()
    dialog = window.findChild(AboutDialog, "aboutDialog")
    assert dialog is not None and dialog.isVisible()
    labels = dialog.findChildren(QLabel)
    text = "\n".join(label.text() for label in labels)
    for value in (__version__, "Björn Rudner", "GPL", "CC BY-SA 4.0", "not affiliated"):
        assert value in text
    assert any(
        anchor.get("href") == "https://rideforces.com/"
        for label in labels
        if label.openExternalLinks()
        for anchor in fromstring(f"<div>{label.text()}</div>").iter("a")
    )
    window.language.setCurrentIndex(1)
    window.appearance.setCurrentIndex(1)
    QApplication.processEvents()
    assert dialog.windowTitle() == "Über Ride Forces Analyzer"
    assert any("Unabhängiges Projekt" in label.text() for label in labels)
    window.about_action.trigger()
    assert len(window.findChildren(AboutDialog)) == 1
    close = next(
        button for button in dialog.findChildren(QPushButton) if button.text() == "Schließen"
    )
    assert close is not None and close.text() == "Schließen"
    close.click()
    assert not dialog.isVisible()
