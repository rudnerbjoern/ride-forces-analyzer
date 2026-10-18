"""Native GUI fixtures and isolated user state; not imported by pure suites."""

# cspell:words autouse

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PySide6.QtCore import QEvent, QThreadPool
from PySide6.QtWidgets import QApplication
from ride_forces_analyzer.config import AppSettings
from ride_forces_analyzer.i18n import get_language, set_language
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.ui.helpers import resize_workspace, wait_until


@pytest.fixture(autouse=True)
def isolated_user_preferences(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """GUI tests and their subprocesses never read or overwrite user preferences."""
    with TemporaryDirectory(dir=".tmp") as directory:
        monkeypatch.setenv("LOCALAPPDATA", str(Path(directory).resolve()))
        original_language = get_language()
        try:
            yield
        finally:
            set_language(original_language)


@pytest.fixture
def explorer_window() -> Iterator[ExplorerWindow]:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    assert isinstance(application, QApplication)
    window = ExplorerWindow(AppSettings(language="en"))
    window.show()
    wait_until(lambda: window.windowHandle().isExposed())
    # Test-controlled minimum size keeps interaction layout independent of the desktop.
    # Logical working area of a 4K desktop at 200%, reserving taskbar space.
    resize_workspace(window, 1920, 1040)
    wait_until(lambda: window.width() == 1920 and window.inspector.isVisible())
    yield window
    window.close()
    QThreadPool.globalInstance().waitForDone()
    QApplication.processEvents()
    window.deleteLater()
    QApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)


@pytest.fixture
def small_preview_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise real preview workers/compositing without drawing five 4K layouts.

    Production frame/preview tests own geometry, alpha and rendered content.
    """
    from PIL import Image
    from ride_forces_analyzer.rendering.frames import OverlayRenderer

    def render_sample(self: OverlayRenderer, position: float) -> Image.Image:
        assert self.timeline.first <= position <= self.timeline.last
        alpha = 0 if self.timeline.settings.output == "transparent" else 255
        return Image.new("RGBA", (8, 8), (0, 0, 0, alpha))

    monkeypatch.setattr(OverlayRenderer, "render_sample", render_sample)
