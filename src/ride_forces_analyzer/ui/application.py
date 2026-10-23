"""Desktop file-open delivery through the existing asynchronous import flow."""

from pathlib import Path

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from ride_forces_analyzer.ui.window import ExplorerWindow


class RecordingApplication(QApplication):
    """Retain the latest desktop request until the explorer can import it."""

    def __init__(self, arguments: list[str]) -> None:
        self.window: ExplorerWindow | None = None
        self.pending_path: Path | None = None
        super().__init__(arguments)
        self.delivery_timer = QTimer(self)
        self.delivery_timer.setInterval(50)
        self.delivery_timer.timeout.connect(self.deliver_file)

    def event(self, event: QEvent) -> bool:
        if isinstance(event, QFileOpenEvent) and event.url().isLocalFile():
            self.pending_path = Path(event.url().toLocalFile())
            if hasattr(self, "delivery_timer"):
                self.deliver_file()
            return True
        return super().event(event)

    def deliver_file(self) -> None:
        """Open pending local files once the window and importer are ready."""
        if self.pending_path is None:
            self.delivery_timer.stop()
            return
        if self.window is None or not self.window.open_action.isEnabled():
            self.delivery_timer.start()
            return
        path, self.pending_path = self.pending_path, None
        self.delivery_timer.stop()
        self.window.open_path(path)
