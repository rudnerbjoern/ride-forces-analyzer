"""Real local sockets forward requests between native processes."""

import json
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep


def test_secondary_forwards_request_and_owner_releases_lock(export_directory: Path) -> None:
    setup = """
import json
from pathlib import Path
import sys
from PySide6.QtCore import QCoreApplication, QTimer
from ride_forces_analyzer import instance
directory = Path(sys.argv[1])
instance.data_directory = lambda: directory
app = QCoreApplication([])
broker = instance.InstanceBroker(app)
"""
    primary = (
        setup
        + """
assert broker.start_or_forward(instance.OpenRequest())
def received(request):
    (directory / "received.json").write_text(request.model_dump_json(), encoding="utf-8")
    QTimer.singleShot(50, app.quit)
broker.requested.connect(received)
(directory / "ready").touch()
QTimer.singleShot(15000, lambda: app.exit(2))
result = app.exec()
broker.close()
raise SystemExit(result)
"""
    )
    process = subprocess.Popen(
        [sys.executable, "-c", primary, str(export_directory)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = monotonic() + 10
        while not (export_directory / "ready").exists() and process.poll() is None:
            assert monotonic() < deadline, "Primary instance did not become ready"
            sleep(0.02)
        client = subprocess.run(
            [
                sys.executable,
                "-c",
                setup
                + """
request = instance.OpenRequest(path=str(directory / "recording with spaces.zforces"), new_window=True)
assert not broker.start_or_forward(request)
""",
                str(export_directory),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert client.returncode == 0, client.stdout + client.stderr
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stdout + stderr
        received = json.loads((export_directory / "received.json").read_text(encoding="utf-8"))
        assert received == {
            "path": str(export_directory / "recording with spaces.zforces"),
            "new_window": True,
        }
        successor = subprocess.run(
            [
                sys.executable,
                "-c",
                setup
                + """
assert broker.start_or_forward(instance.OpenRequest())
broker.close()
""",
                str(export_directory),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert successor.returncode == 0, successor.stdout + successor.stderr
        crashed = subprocess.run(
            [
                sys.executable,
                "-c",
                setup
                + """
import os
assert broker.start_or_forward(instance.OpenRequest())
os._exit(0)
""",
                str(export_directory),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert crashed.returncode == 0, crashed.stdout + crashed.stderr
        recovered = subprocess.run(
            [
                sys.executable,
                "-c",
                setup
                + """
assert broker.start_or_forward(instance.OpenRequest())
broker.close()
""",
                str(export_directory),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
