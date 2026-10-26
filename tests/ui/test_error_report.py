"""Quiet report availability across windows and native folder opening."""

# cspell:words qapp pixmap

from pathlib import Path
from threading import Thread

from PySide6.QtCore import QEvent, QSize, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication
import pytest

from ride_forces_analyzer.runtime import error_reporting
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.ui.presentation.error_report import ErrorReportButton
from tests.ui.helpers import wait_until


def test_error_report_indicator_shares_state_and_opens_report_folder(
    qapp: QApplication,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = error_reporting.ErrorReportStatus()
    monkeypatch.setattr(error_reporting, "report_status", status)
    opened: list[QUrl] = []

    def open_url(url: QUrl) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", open_url)
    windows = [ExplorerWindow(AppSettings()), ExplorerWindow(AppSettings())]
    try:
        buttons: list[ErrorReportButton] = []
        for window in windows:
            window.set_appearance(2)
            window.show()
            button = window.findChild(ErrorReportButton, "errorReportIndicator")
            assert button is not None and button.isHidden()
            buttons.append(button)
        report = export_directory / "Support folder" / "error-report-123.txt"
        thread = Thread(target=lambda: status.recorded(report))
        thread.start()
        thread.join()
        wait_until(lambda: all(button.isVisible() for button in buttons))
        for button in buttons:
            assert not button.icon().isNull()
            assert button.iconSize() == QSize(20, 20)
            icon = button.icon().pixmap(QSize(20, 20)).toImage()
            yellow = icon.pixelColor(
                int(10 * icon.devicePixelRatio()),
                int(5 * icon.devicePixelRatio()),
            )
            rendered = button.grab().toImage()
            colored_columns = [
                x
                for x in range(rendered.width())
                if any(rendered.pixelColor(x, y) == yellow for y in range(rendered.height()))
            ]
            assert colored_columns
            assert max(colored_columns) - min(colored_columns) + 1 >= (
                14 * rendered.devicePixelRatio()
            )
            assert button.toolTip() and button.accessibleName()
            button.click()
        assert [Path(url.toLocalFile()) for url in opened] == [report.parent] * 2
        assert all(url.isLocalFile() for url in opened)
        late = ErrorReportButton(windows[0].statusBar())
        assert not late.isHidden()
        qapp.processEvents()
        assert all(button.isVisible() for button in buttons)
    finally:
        for window in windows:
            window.close()
            window.deleteLater()
            QApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
