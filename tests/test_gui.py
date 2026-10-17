"""Exercise the actual module entry point in a separate Qt process."""

import os
import subprocess
import sys
from textwrap import dedent

import pytest


@pytest.mark.parametrize("scale_factor", ["1", "2"])
@pytest.mark.parametrize("custom_settings", [False, True], ids=["default", "custom"])
def test_application_starts_and_closes(custom_settings: bool, scale_factor: str) -> None:
    title = "Custom window" if custom_settings else "Ride Forces Analyzer"
    size = (720, 480) if custom_settings else (1280, 820)
    launch = (
        "from ride_forces_analyzer.config import AppSettings\n"
        "from ride_forces_analyzer.__main__ import main\n"
        "raise SystemExit(main(AppSettings(window_title='Custom window', "
        "window_width=720, window_height=480)))"
        if custom_settings
        else 'runpy.run_module("ride_forces_analyzer", run_name="__main__")'
    )
    script = dedent("""
        import runpy
        import sys

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

        original_show = QMainWindow.show
        original_exec = QApplication.exec
        failures = []
        inspected = []

        def checked_show(self):
            assert (self.width(), self.height()) == EXPECTED_SIZE
            original_show(self)

        def inspect_window():
            try:
                windows = QApplication.topLevelWidgets()
                assert len(windows) == 1
                window = windows[0]
                assert isinstance(window, QMainWindow)
                assert window.isVisible()
                assert window.windowHandle().isExposed()
                assert window.windowTitle() == EXPECTED_TITLE
                assert not window.windowIcon().isNull()
                assert all(label.text() != "Ride Forces Analyzer"
                           for label in window.findChildren(QLabel))
                available = window.screen().availableGeometry()
                frame = window.frameGeometry()
                actual = (window.width(), window.height())
                margins = (frame.width() - window.width(),
                           frame.height() - window.height())
                limits = (available.width(), available.height())
                for measured, requested, decoration, limit in zip(
                        actual, EXPECTED_SIZE, margins, limits, strict=True):
                    assert measured == requested or (
                        requested + decoration > limit and 0 < measured < requested
                    ), (actual, EXPECTED_SIZE, available, frame)
                heading = window.findChild(QLabel, "recordingHeading")
                assert heading is not None
                assert "Open a .forces recording" in heading.text()
                if sys.platform == "win32":
                    assert QApplication.platformName() == "windows"
                window.resize(800, 500)
                assert (window.width(), window.height()) == (800, 500)
                inspected.append(True)
                assert window.close()
                assert not window.isVisible()
            except BaseException as error:
                failures.append(error)
                QApplication.instance().quit()

        def checked_exec(self):
            QTimer.singleShot(500, inspect_window)
            result = original_exec()
            if failures:
                raise failures[0]
            assert inspected, "Qt event loop did not execute the inspection"
            assert result == 0
            print("GUI smoke passed: startup, exposure, content, resize, close")
            return result

        QMainWindow.show = checked_show
        QApplication.exec = checked_exec
        LAUNCH_APPLICATION
    """)
    script = (
        script.replace("EXPECTED_TITLE", repr(title))
        .replace("EXPECTED_SIZE", repr(size))
        .replace("LAUNCH_APPLICATION", launch)
    )
    environment = os.environ.copy()
    environment["QT_SCALE_FACTOR"] = scale_factor
    if sys.platform == "win32":
        environment["QT_QPA_PLATFORM"] = "windows"
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GUI smoke passed" in result.stdout
    print(result.stdout.strip())
