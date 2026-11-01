"""Own recording windows and route command-line, desktop and local IPC requests."""

from collections import deque
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, Slot
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.runtime.instance import OpenRequest
from ride_forces_analyzer.i18n import get_language
from ride_forces_analyzer.storage.library import LibraryStore


class RecordingApplication(QApplication):
    """Keep analysis/view state in separate windows within one application.

    Attributes:
        windows: Open explorer windows owned by the application.
        pending_requests: Recording-open requests awaiting application readiness.
        ready: Callback invoked when initialization completes.
        settings: Validated settings controlling this operation.
        delivery_timer: Timer scheduling delivery timer.
    """

    def __init__(self, arguments: list[str]) -> None:
        """Initialize the recording application and its state.

        Args:
            arguments: Command-line arguments to interpret.

        Returns:
            None.
        """
        self.windows: list[ExplorerWindow] = []
        self.pending_requests: deque[OpenRequest] = deque()
        self.ready = False
        super().__init__(arguments)
        self.settings = AppSettings()
        self.delivery_timer = QTimer(self)
        self.delivery_timer.setInterval(50)
        self.delivery_timer.timeout.connect(self.deliver_requests)

    def event(self, event: QEvent) -> bool:
        """Handle application file-open events and delegate other events to Qt.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            True when the requested check succeeds or the event is handled; otherwise False.
        """
        if isinstance(event, QFileOpenEvent) and event.url().isLocalFile():
            self.pending_requests.append(OpenRequest(path=event.url().toLocalFile()))
            if hasattr(self, "delivery_timer"):
                self.deliver_requests()
            return True
        return super().event(event)

    def start(self, request: OpenRequest) -> None:
        """Initialize the Library, then create the initial recording window.

        Args:
            request: Request carrying the inputs and context for this operation.

        Returns:
            None.

        Raises:
            LibraryStoreError: Library initialization failed; no window is created.
        """
        LibraryStore().initialize()
        self.create_window(
            Path(request.path) if request.path is not None else None,
            restore_last_file=request.path is None
            and not request.new_window
            and not self.pending_requests,
        )
        self.ready = True
        self.deliver_requests()

    def create_window(
        self,
        path: Path | None = None,
        *,
        restore_last_file: bool = False,
    ) -> ExplorerWindow:
        """Create and register an independently owned recording window.

        Args:
            path: Filesystem path read or written by this operation.
            restore_last_file: Whether startup may reopen the last recording.

        Returns:
            Registered explorer window owned by the application.
        """
        appearance = self.windows[0].appearance_preference if self.windows else None
        settings = (
            self.settings.model_copy(update={"language": get_language()})
            if self.windows
            else self.settings
        )
        window = ExplorerWindow(settings, restore_last_file=restore_last_file)
        self.windows.append(window)
        if appearance is not None and window.appearance_preference is not appearance:
            window.appearance_preference = appearance
            window.apply_appearance()
        window.new_window_requested.connect(self._new_window_requested)
        window.closed.connect(lambda: self._closed(window))
        window.show()
        if path is not None:
            window.open_path(path)
        return window

    @Slot(object)
    def _new_window_requested(self, path: object) -> None:
        if isinstance(path, Path):
            self.receive_request(OpenRequest(path=str(path.resolve()), new_window=True))

    def _closed(self, window: ExplorerWindow) -> None:
        if window in self.windows:
            self.windows.remove(window)
        window.deleteLater()

    @Slot(object)
    def receive_request(self, request: object) -> None:
        """Queue a file-open request received from the local instance broker.

        Args:
            request: Request carrying the inputs and context for this operation.

        Returns:
            None.
        """
        if isinstance(request, OpenRequest):
            self.pending_requests.append(request)
            self.deliver_requests()

    @staticmethod
    def _activate(window: ExplorerWindow) -> None:
        if window.isMinimized():
            window.showNormal()
        window.raise_()
        window.activateWindow()

    def deliver_requests(self) -> None:
        """Retain requests while an existing target window is importing.

        Returns:
            None.
        """
        if not self.ready:
            self.delivery_timer.start()
            return
        while self.pending_requests:
            request = self.pending_requests[0]
            path = Path(request.path).resolve() if request.path is not None else None
            if not request.new_window and path is not None:
                existing = next(
                    (window for window in self.windows if window.recording_path == path),
                    None,
                )
                if existing is not None:
                    self.pending_requests.popleft()
                    self._activate(existing)
                    continue
            active = self.activeWindow()
            while active is not None and not isinstance(active, ExplorerWindow):
                active = active.parentWidget()
            target = (
                active
                if isinstance(active, ExplorerWindow) and active in self.windows
                else next(iter(self.windows), None)
            )
            if request.new_window or target is None:
                target = self.create_window(path)
            elif path is not None:
                if not target.open_action.isEnabled():
                    self.delivery_timer.start()
                    return
                target.open_path(path)
            self.pending_requests.popleft()
            self._activate(target)
        self.delivery_timer.stop()
