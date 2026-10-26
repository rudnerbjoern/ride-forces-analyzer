"""Status-bar access to the current process's successfully written error report."""

# cspell:words Pixmap linejoin linecap

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QToolButton, QWidget

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime import error_reporting
from .translation import bind


class ErrorReportButton(QToolButton):
    """Show a quiet warning icon and open the report's directory on request."""

    def __init__(self, parent: QWidget) -> None:
        """Connect report availability with queued delivery on the UI thread.

        Args:
            parent: Owning status bar or recording window.
        """
        super().__init__(parent)
        self.setObjectName("errorReportIndicator")
        self.setAutoRaise(True)
        self.setStyleSheet("QToolButton#errorReportIndicator { padding: 0; }")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        image = QImage(40, 40, QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
            b'<path d="M10 1.5 L19 18 H1 Z" fill="#ffd43b" '
            b'stroke="#171717" stroke-width="1" stroke-linejoin="round"/>'
            b'<path d="M10 7 V12" stroke="#171717" stroke-width="2" '
            b'stroke-linecap="round"/>'
            b'<circle cx="10" cy="15" r="1.1" fill="#171717"/></svg>',
        )
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.setDevicePixelRatio(2)
        self.setIcon(QIcon(QPixmap.fromImage(image)))
        self.setIconSize(QSize(20, 20))
        self.setFixedSize(24, 24)
        bind(self, tr("Error report available — open folder"), "toolTip")
        bind(self, tr("Error report available — open folder"), "accessibleName")
        self._directory: Path | None = None
        self.hide()
        status = error_reporting.report_status
        status.available.connect(self._report_available, Qt.ConnectionType.QueuedConnection)
        if status.path is not None:
            self._report_available(str(status.path))
        self.clicked.connect(self._open_folder)

    @Slot(str)
    def _report_available(self, report: str) -> None:
        """Reveal access to a report delivered on the UI thread.

        Args:
            report: Path of the current process's written report.
        """
        self._directory = Path(report).parent
        self.show()

    @Slot()
    def _open_folder(self) -> None:
        """Ask the native file manager to open the available report directory."""
        if self._directory is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._directory)))
