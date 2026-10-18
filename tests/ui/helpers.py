"""Native GUI event waits and controlled workspace sizing."""

from collections.abc import Callable
import time

from PySide6.QtTest import QTest
from ride_forces_analyzer.ui.window import ExplorerWindow


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
