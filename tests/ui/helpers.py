"""Native GUI event waits and controlled workspace sizing."""

from collections.abc import Callable
import time
from math import gcd

from PIL import Image
from ride_forces_analyzer.rendering.layouts import resolve_geometry
from ride_forces_analyzer.rendering.model import ExportTimeline, VideoOutput

from PySide6.QtTest import QTest
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow


def wait_until(predicate: Callable[[], bool], timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("Native GUI operation timed out")
        QTest.qWait(10)
        time.sleep(0.001)  # Let Python import workers acquire the GIL during cold startup.


def resize_workspace(window: ExplorerWindow, width: int, height: int) -> None:
    """Exercise a real layout even when Windows limits normal desktop tracking."""
    window.setMinimumSize(width, height)
    window.resize(width, height)
    wait_until(lambda: (window.width(), window.height()) == (width, height))
    QTest.qWait(50)


class SmallPreviewRenderer:
    """Supply tiny proportional frames without constructing production layout renderers."""

    def __init__(self, timeline: ExportTimeline) -> None:
        self.timeline = timeline

    def render_sample(self, position: float) -> Image.Image:
        assert self.timeline.first <= position <= self.timeline.last
        alpha = 0 if self.timeline.settings.output == VideoOutput.TRANSPARENT else 255
        width, height = resolve_geometry(self.timeline.settings).output_size
        divisor = gcd(width, height)
        return Image.new("RGBA", (width // divisor, height // divisor), (0, 0, 0, alpha))
