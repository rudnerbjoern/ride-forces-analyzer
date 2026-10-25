"""Real local sockets forward requests between native processes."""

# cspell:words qapp qtbot pytestqt msleep

import json
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep

import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot


def test_secondary_forwards_request_and_owner_releases_lock(export_directory: Path) -> None:
    setup = """
import json
from pathlib import Path
import sys
from PySide6.QtCore import QCoreApplication, QTimer
from ride_forces_analyzer.runtime import instance
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


def test_instance_startup_failures_never_create_a_competing_owner(
    qapp: "QApplication",
    export_directory: Path,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    from itertools import count
    from unittest.mock import Mock

    from PySide6.QtCore import QByteArray, QLockFile
    from ride_forces_analyzer.runtime import instance

    monkeypatch.setattr(instance, "data_directory", lambda: export_directory)
    broker = instance.InstanceBroker(qapp)
    broker.close()  # No lock was acquired, so this is a no-op.
    lock, server = Mock(), Mock()
    monkeypatch.setattr(broker, "lock", lock)
    monkeypatch.setattr(broker, "server", server)
    lock.tryLock.return_value = True
    server.listen.return_value = False
    server.errorString.return_value = "Unavailable socket"
    with pytest.raises(RuntimeError, match="Unable to start local file-open service"):
        broker.start_or_forward(instance.OpenRequest())
    lock.unlock.assert_called_once()
    lock.tryLock.return_value = False
    lock.error.return_value = QLockFile.LockError.PermissionError
    with pytest.raises(RuntimeError, match="Unable to acquire application instance lock"):
        broker.start_or_forward(instance.OpenRequest())
    lock.error.return_value = QLockFile.LockError.LockFailedError

    def skip_sleep(delay: int) -> None:
        pass

    monkeypatch.setattr(instance.QThread, "msleep", skip_sleep)
    for mode, message in (
        ("rejected", "rejected the file-open request"),
        ("unacknowledged", "did not acknowledge"),
        ("unavailable", "Unable to contact"),
    ):
        ticks = count(0, 2)
        monkeypatch.setattr(instance, "monotonic", lambda: float(next(ticks)))
        socket = Mock()
        socket.waitForConnected.return_value = mode != "unavailable"
        socket.readAll.return_value = QByteArray(b"ERROR\n" if mode == "rejected" else b"")
        monkeypatch.setattr(instance, "QLocalSocket", Mock(return_value=socket))
        with pytest.raises(RuntimeError, match=message):
            broker.start_or_forward(instance.OpenRequest(path="ride.forces"))
        if mode == "unavailable":
            socket.abort.assert_called()
    assert lock.unlock.call_count == 1


def test_owner_rejects_invalid_and_oversized_messages_and_accepts_fragments(
    qapp: "QApplication",
    qtbot: "QtBot",
    export_directory: Path,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    from PySide6.QtNetwork import QLocalSocket
    from ride_forces_analyzer.runtime import instance

    monkeypatch.setattr(instance, "data_directory", lambda: export_directory)
    broker = instance.InstanceBroker(qapp)
    received: list[instance.OpenRequest] = []
    broker.requested.connect(received.append)
    assert broker.start_or_forward(instance.OpenRequest())
    try:
        for payload, response in ((b'{"unknown":true}\n', b"ERROR\n"), (b"x" * (256 * 1024), b"")):
            client = QLocalSocket()
            client.connectToServer(broker.name)
            assert client.waitForConnected(1000)
            client.write(payload)
            client.flush()
            qtbot.waitUntil(
                lambda: client.state() == QLocalSocket.LocalSocketState.UnconnectedState,
            )
            assert bytes(client.readAll().data()) == response
        assert received == []
        client = QLocalSocket()
        client.connectToServer(broker.name)
        assert client.waitForConnected(1000)
        client.write(b'{"path":')
        client.flush()
        qapp.processEvents()
        assert not received
        client.write(b'"ride.forces"}\n')
        client.flush()
        qtbot.waitUntil(lambda: bool(received))
        qtbot.waitUntil(lambda: client.bytesAvailable() > 0)
        assert bytes(client.readAll().data()) == b"OK\n"
        assert received == [instance.OpenRequest(path="ride.forces")]
    finally:
        broker.close()
        broker.close()


def test_posix_socket_path_is_prepared_in_a_private_directory(
    qapp: "QApplication",
    export_directory: Path,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    from ride_forces_analyzer.runtime import instance

    monkeypatch.setattr(instance, "data_directory", lambda: export_directory / "data")
    monkeypatch.setattr(instance, "gettempdir", lambda: str(export_directory))
    with monkeypatch.context() as patch:
        patch.setattr(instance.sys, "platform", "linux")
        broker = instance.InstanceBroker(qapp)
    socket = Path(broker.name)
    assert socket.name == "socket"
    assert socket.parent.parent == export_directory
    assert socket.parent.is_dir()
    broker.close()
