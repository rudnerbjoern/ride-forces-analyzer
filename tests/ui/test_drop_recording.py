"""Recording drops share the normal importer and reject unrelated payloads."""

from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


def drop_events(urls: list[QUrl]) -> tuple[QMimeData, QDragEnterEvent, QDropEvent]:
    mime = QMimeData()
    mime.setUrls(urls)
    enter = QDragEnterEvent(
        QPoint(20, 20),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    drop = QDropEvent(
        QPointF(20, 20),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    return mime, enter, drop


def test_drop_imports_recording(explorer_window: ExplorerWindow) -> None:
    for extension in ("forces", "zforces"):
        path = next(REAL_FIXTURE_DIRECTORY.glob(f"Manta*.{extension}"))
        mime, enter, drop = drop_events([QUrl.fromLocalFile(str(path.resolve()))])
        explorer_window.dragEnterEvent(enter)
        assert enter.isAccepted()
        explorer_window.dropEvent(drop)
        assert drop.isAccepted()
        assert mime.hasUrls()
        # A second drop must not replace an active import.
        _, busy_enter, busy_drop = drop_events([QUrl.fromLocalFile(str(path.resolve()))])
        explorer_window.dragEnterEvent(busy_enter)
        explorer_window.dropEvent(busy_drop)
        assert not busy_enter.isAccepted() and not busy_drop.isAccepted()
        wait_until(
            lambda: explorer_window.data is not None and explorer_window.open_action.isEnabled(),
        )
        assert explorer_window.data is not None and explorer_window.data.title == "Manta"


def test_drop_rejects_unrelated_payloads(
    explorer_window: ExplorerWindow,
    export_directory: Path,
) -> None:
    recording = next(REAL_FIXTURE_DIRECTORY.glob("Manta*.forces")).resolve()
    unrelated = export_directory / "notes.txt"
    unrelated.write_text("Not a recording", encoding="utf-8")
    for urls in (
        [],
        [QUrl("https://example.org/recording.forces")],
        [QUrl.fromLocalFile(str(unrelated))],
        [QUrl.fromLocalFile(str(export_directory))],
        [QUrl.fromLocalFile(str(recording))] * 2,
    ):
        mime, enter, drop = drop_events(urls)
        explorer_window.dragEnterEvent(enter)
        explorer_window.dropEvent(drop)
        assert not enter.isAccepted() and not drop.isAccepted()
        assert mime is not None
    assert explorer_window.data is None
