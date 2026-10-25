"""Desktop file events use normal imports, including compressed recordings."""

import subprocess
import sys

import pytest

from tests.support.recordings import REAL_FIXTURE_DIRECTORY


@pytest.mark.parametrize("module", ["ride_forces_analyzer", "scripts.windows_entry"])
def test_entry_point_passes_positional_path(module: str) -> None:
    program = """
import runpy
import sys
from pathlib import Path
import ride_forces_analyzer.__main__ as entry
import ride_forces_analyzer.ui.application as application
import ride_forces_analyzer.runtime.instance as instance
from types import SimpleNamespace
class Finished(Exception):
    pass
def check(*args, **kwargs):
    assert kwargs.get("recording") == Path("recordings with spaces/Manta.zforces")
    assert kwargs.get("new_window") is True
    print("Argument passed", flush=True)
    raise Finished
if sys.argv[1] == "scripts.windows_entry":
    entry.main = check
else:
    application.RecordingApplication = lambda args: SimpleNamespace(
        setDesktopFileName=lambda name: None, receive_request=lambda request: None)
    def forward(request):
        return check(recording=Path(request.path).relative_to(Path.cwd()), new_window=request.new_window)
    instance.InstanceBroker = lambda app: SimpleNamespace(
        requested=SimpleNamespace(connect=lambda slot: None), start_or_forward=forward)
module = sys.argv[1]
sys.argv = [module, "recordings with spaces/Manta.zforces", "--new-window"]
try:
    runpy.run_module(module, run_name="__main__")
except Finished:
    pass
"""
    result = subprocess.run(
        [sys.executable, "-c", program, module],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Argument passed" in result.stdout


@pytest.mark.parametrize("extension", ["forces", "zforces"])
def test_desktop_file_request_waits_for_window_and_imports(extension: str) -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob(f"Manta*.{extension}"))
    program = """
import sys
from pathlib import Path
from PySide6.QtCore import QTimer, QThreadPool
from PySide6.QtGui import QFileOpenEvent
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.runtime.instance import OpenRequest
from ride_forces_analyzer.ui.application import RecordingApplication
app = RecordingApplication([])
path = Path(sys.argv[1])
assert app.event(QFileOpenEvent(str(path)))
assert Path(app.pending_requests[0].path) == path
app.settings = AppSettings(language=Language.ENGLISH)
app.start(OpenRequest())
window = app.windows[0]
timer = QTimer()
def check():
    if window.data is not None and window.open_action.isEnabled():
        assert window.data.title == "Manta"
        assert not app.pending_requests
        print("File-open import passed", flush=True)
        window.close()
        app.quit()
timer.timeout.connect(check)
timer.start(20)
QTimer.singleShot(20000, lambda: app.exit(2))
result = app.exec()
QThreadPool.globalInstance().waitForDone()
raise SystemExit(result)
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(path.resolve())],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "File-open import passed" in result.stdout
