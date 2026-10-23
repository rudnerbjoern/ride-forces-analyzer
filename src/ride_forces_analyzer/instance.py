"""Single-process ownership and local file-open request transport, without widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words msleep

from hashlib import sha256
from pathlib import Path
import sys
from tempfile import gettempdir
from time import monotonic

from pydantic import BaseModel, ValidationError
from PySide6.QtCore import QLockFile, QObject, QThread, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ride_forces_analyzer.runtime_paths import data_directory


class OpenRequest(BaseModel, frozen=True, strict=True, extra="forbid"):
    path: str | None = None
    new_window: bool = False


class InstanceBroker(QObject):
    """Hold a process lock or forward one acknowledged request to its owner."""

    requested = Signal(object)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        directory = data_directory()
        directory.mkdir(parents=True, exist_ok=True)
        identity = sha256(str(directory.resolve()).encode("utf-8")).hexdigest()[:20]
        self.name = f"ride-forces-analyzer-{identity}"
        if sys.platform != "win32":
            private = Path(gettempdir()) / f"rfa-{identity}"
            private.mkdir(mode=0o700, exist_ok=True)
            private.chmod(0o700)
            self.name = str(private / "socket")
        self.lock = QLockFile(str(directory / "instance.lock"))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._connected)

    def start_or_forward(self, request: OpenRequest) -> bool:
        """Return True for the owner, False after acknowledged forwarding.

        A bounded startup retry allows the lock owner to finish opening its server.
        Failure never starts a competing owner or removes another owner's socket.
        """
        if self.lock.tryLock(0):
            QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError(
                    f"Unable to start local file-open service: {self.server.errorString()}",
                )
            return True
        if self.lock.error() is not QLockFile.LockError.LockFailedError:
            raise RuntimeError("Unable to acquire application instance lock")
        deadline = monotonic() + 5
        while monotonic() < deadline:
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if socket.waitForConnected(100):
                payload = request.model_dump_json().encode("utf-8") + b"\n"
                socket.write(payload)
                socket.flush()
                response = bytearray()
                while monotonic() < deadline:
                    response.extend(socket.readAll().data())
                    if b"\n" in response:
                        socket.disconnectFromServer()
                        if bytes(response) == b"OK\n":
                            return False
                        raise RuntimeError("The running application rejected the file-open request")
                    socket.waitForReadyRead(100)
                raise RuntimeError(
                    "The running application did not acknowledge the file-open request",
                )
            socket.abort()
            QThread.msleep(50)
        raise RuntimeError(
            "Unable to contact the running application; no second instance was started",
        )

    def _connected(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self._read_request(socket)

    def _read_request(self, socket: QLocalSocket) -> None:
        socket.setParent(self)
        socket.setReadBufferSize(256 * 1024)
        timer = QTimer(socket)
        timer.setSingleShot(True)
        timer.timeout.connect(socket.abort)
        timer.start(5000)
        socket.disconnected.connect(socket.deleteLater)
        buffer = bytearray()

        def read() -> None:
            buffer.extend(socket.readAll().data())
            if len(buffer) >= 256 * 1024:
                socket.abort()
                return
            if b"\n" not in buffer:
                return
            timer.stop()
            try:
                request = OpenRequest.model_validate_json(bytes(buffer).strip())
            except ValidationError:
                socket.write(b"ERROR\n")
            else:
                self.requested.emit(request)
                socket.write(b"OK\n")
            socket.flush()
            socket.disconnectFromServer()

        socket.readyRead.connect(read)
        read()

    def close(self) -> None:
        """Release only this broker's ownership after application shutdown."""
        if self.server.isListening():
            self.server.close()
            self.lock.unlock()
