"""Independent recording windows share only application preferences."""

# cspell:words neuem Fenster öffnen

import subprocess
import sys

from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_compare_windows_route_files_and_keep_independent_state() -> None:
    taron = next(REAL_FIXTURE_DIRECTORY.glob("Taron*.forces")).resolve()
    manta = next(REAL_FIXTURE_DIRECTORY.glob("Manta*.zforces")).resolve()
    program = """
from pathlib import Path
import sys
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QFileDialog
from ride_forces_analyzer.config import AppSettings
from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.instance import OpenRequest
from ride_forces_analyzer.ui.application import RecordingApplication
from tests.ui.helpers import wait_until
app = RecordingApplication([])
app.settings = AppSettings(language=Language.ENGLISH)
app.start(OpenRequest(path=sys.argv[1]))
first = app.windows[0]
wait_until(lambda: first.data is not None and first.open_action.isEnabled())
original = first.data.analysis
first.preferences.remember_restore_last_file(True)
QFileDialog.getOpenFileName = lambda *args, **kwargs: (sys.argv[2], "")
first.new_window_action.trigger()
assert len(app.windows) == 2
second = app.windows[1]
wait_until(lambda: second.data is not None and second.open_action.isEnabled())
assert first.data.analysis is original
assert first.data.source.source_sha256 != second.data.source.source_sha256
assert first.analysis_controller is not second.analysis_controller
assert first.playback is not second.playback
sample = second.slider.value()
first.slider.setValue(first.slider.value() + 1)
assert second.slider.value() == sample
second_range = (second.axis_x.min(), second.axis_x.max())
first.axis_x.setRange(first.axis_x.min() + 1, first.axis_x.max() - 1)
assert (second.axis_x.min(), second.axis_x.max()) == second_range
app.receive_request(OpenRequest(path=sys.argv[1]))
assert len(app.windows) == 2 and first.data.analysis is original
first.set_ui_language(1)
assert all(window.ui_language == "de" for window in app.windows)
assert second.new_window_action.text() == "In neuem Fenster öffnen …"
first.set_appearance(1)
assert first.theme is second.theme
# Explicit new windows do not restore the previously opened recording.
first._preview_appearance(2)
app.receive_request(OpenRequest(new_window=True))
blank = app.windows[-1]
app.processEvents()
assert blank.data is None and blank.recording_path is None
assert blank.theme is first.theme is second.theme
first._preview_appearance(1)
assert blank.close()
assert len(app.windows) == 2
# Force a separate view of the same recording for comparison.
app.receive_request(OpenRequest(path=sys.argv[1], new_window=True))
third = app.windows[-1]
wait_until(lambda: third.data is not None and third.open_action.isEnabled())
assert third is not first and third.data.analysis is not first.data.analysis
assert first.close()
assert len(app.windows) == 2 and second.data is not None
assert third.close()
assert second.close()
QThreadPool.globalInstance().waitForDone()
app.processEvents()
print("Independent recording windows passed")
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(taron), str(manta)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Independent recording windows passed" in result.stdout
