"""Authenticated loopback transport for the separate Stream Deck plugin.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words WebSockets

from functools import partial
import json
from pathlib import Path
from secrets import compare_digest, token_hex

from pydantic import BaseModel, Field, ValidationError
from PySide6.QtCore import QFileDevice, QIODevice, QObject, QSaveFile, QTimer, Signal
from PySide6.QtNetwork import QHostAddress
from PySide6.QtWebSockets import QWebSocket, QWebSocketProtocol, QWebSocketServer

from ride_forces_analyzer.runtime.paths import data_directory

TRANSPORT_VERSION = 1
MAX_MESSAGE_BYTES = 64 * 1024


class _Hello(BaseModel, frozen=True, strict=True, extra="forbid"):
    """First-frame authentication, independent of application commands.

    Attributes:
        version: Supported transport handshake version.
        token: Private discovery-file credential for this server session.
    """

    version: int = Field(ge=TRANSPORT_VERSION, le=TRANSPORT_VERSION)
    token: str = Field(pattern=r"^[a-f0-9]{64}$")


class ControlServer(QObject):
    """Exchange text frames on the owning Qt thread after authentication.

    Attributes:
        received: Signal carrying authenticated application text frames.
        endpoint_path: Private discovery file shared with the plugin.
        server: Qt server bound exclusively to IPv4 loopback.
    """

    received = Signal(str)

    def __init__(self, endpoint_path: Path | None = None, parent: QObject | None = None) -> None:
        """Create a stopped transport without opening sockets or files.

        Args:
            endpoint_path: Discovery-file override for isolated runs.
            parent: Qt owner of this transport.
        """
        super().__init__(parent)
        self.endpoint_path = endpoint_path or data_directory() / "stream-deck.json"
        self.server = QWebSocketServer(
            "Ride Forces Analyzer",
            QWebSocketServer.SslMode.NonSecureMode,
            self,
        )
        self.server.newConnection.connect(self._accept)
        self._clients: set[QWebSocket] = set()
        self._authenticated: set[QWebSocket] = set()
        self._token = ""
        self._published: bytes | None = None
        self._state: str | None = None

    def start(self) -> None:
        """Listen on a dynamic loopback port and atomically publish discovery.

        Raises:
            RuntimeError: If already listening or the loopback socket cannot open.
            OSError: If private discovery cannot be published.
        """
        if self.server.isListening():
            raise RuntimeError("Stream Deck transport is already listening")
        if not self.server.listen(QHostAddress("127.0.0.1"), 0):
            raise RuntimeError(self.server.errorString())
        self._token = token_hex(32)
        payload = json.dumps(
            {
                "version": TRANSPORT_VERSION,
                "port": self.server.serverPort(),
                "token": self._token,
            },
        ).encode("utf-8")
        try:
            self.endpoint_path.parent.mkdir(parents=True, exist_ok=True)
            target = QSaveFile(str(self.endpoint_path))
            if not target.open(QIODevice.OpenModeFlag.WriteOnly):
                raise OSError(target.errorString())
            if not target.setPermissions(
                QFileDevice.Permission.ReadOwner | QFileDevice.Permission.WriteOwner,
            ):
                target.cancelWriting()
                raise OSError("Unable to restrict Stream Deck discovery permissions")
            if target.write(payload) != len(payload) or not target.commit():
                target.cancelWriting()
                raise OSError("Unable to publish Stream Deck discovery")
        except OSError:
            self.server.close()
            raise
        self._published = payload

    def publish_state(self, message: str) -> None:
        """Broadcast current state and retain it for authenticated reconnects.

        Args:
            message: Application-owned text; the transport does not interpret it.

        Raises:
            ValueError: If the UTF-8 payload exceeds the transport frame limit.
        """
        if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("Stream Deck state exceeds the transport message limit")
        self._state = message
        for client in tuple(self._authenticated):
            client.sendTextMessage(message)

    def close(self) -> None:
        """Disconnect peers and remove discovery only if it is still ours.

        Raises:
            OSError: If an owned discovery file cannot be read or removed.
        """
        self.server.close()
        for client in tuple(self._clients):
            client.abort()
        published, self._published = self._published, None
        if published is not None:
            try:
                current = self.endpoint_path.read_bytes()
            except FileNotFoundError:
                return
            if current == published:
                self.endpoint_path.unlink(missing_ok=True)

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            client = self.server.nextPendingConnection()
            if not client.peerAddress().isLoopback() or client.origin():
                client.close(QWebSocketProtocol.CloseCode.CloseCodePolicyViolated)
                client.deleteLater()
                continue
            self._clients.add(client)
            client.setMaxAllowedIncomingMessageSize(MAX_MESSAGE_BYTES)
            client.setMaxAllowedIncomingFrameSize(MAX_MESSAGE_BYTES)
            deadline = QTimer(client)
            deadline.setSingleShot(True)
            deadline.timeout.connect(client.abort)
            deadline.start(5000)
            client.textMessageReceived.connect(partial(self._receive, client, deadline))
            client.binaryMessageReceived.connect(client.abort)
            client.disconnected.connect(partial(self._discard, client))

    def _receive(self, client: QWebSocket, deadline: QTimer, message: str) -> None:
        if client not in self._authenticated:
            try:
                hello = _Hello.model_validate_json(message)
            except ValidationError:
                client.close(QWebSocketProtocol.CloseCode.CloseCodePolicyViolated)
                return
            if not compare_digest(hello.token, self._token):
                client.close(QWebSocketProtocol.CloseCode.CloseCodePolicyViolated)
                return
            deadline.stop()
            self._authenticated.add(client)
            client.sendTextMessage(json.dumps({"transport": "ready", "version": TRANSPORT_VERSION}))
            if self._state is not None:
                client.sendTextMessage(self._state)
            return
        self.received.emit(message)

    def _discard(self, client: QWebSocket) -> None:
        self._authenticated.discard(client)
        self._clients.discard(client)
        client.deleteLater()
