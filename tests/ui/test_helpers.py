"""Native wait polling retains Qt delivery, Python workers and timeout failures."""

# cspell:words qapp

from threading import Event, Thread
from time import monotonic

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication
import pytest

from tests.ui.helpers import wait_until


def test_wait_until_delivers_timers_deferred_deletion_workers_and_timeout(
    qapp: QApplication,
) -> None:
    assert QApplication.instance() is qapp
    observed: list[str] = []
    target = QObject(qapp)
    target.destroyed.connect(lambda: observed.append("destroyed"))
    target.deleteLater()
    QTimer.singleShot(10, lambda: observed.append("timer"))
    completed = Event()

    def finish() -> None:
        completed.wait(0.025)
        completed.set()

    worker = Thread(target=finish)
    worker.start()
    try:
        wait_until(lambda: completed.is_set() and len(observed) == 2)
    finally:
        worker.join(timeout=1)
    assert not worker.is_alive()
    assert sorted(observed) == ["destroyed", "timer"]
    started = monotonic()
    with pytest.raises(AssertionError, match="^Native GUI operation timed out$"):
        wait_until(lambda: False, timeout=0.02)
    assert monotonic() - started >= 0.02
