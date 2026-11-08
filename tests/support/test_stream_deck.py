"""Native application-owned Qt transport and access checks."""

# cspell:words qapp qtbot pytestqt

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from ride_forces_analyzer.runtime.stream_deck import (
    ControlServer,
    TRANSPORT_VERSION,
    MAX_MESSAGE_BYTES,
)


@pytest.mark.qt_log_level_fail("WARNING")
def test_qt_authentication_state_exchange_and_discovery_ownership(
    qapp: QApplication,
    qtbot: QtBot,
    export_directory: Path,
) -> None:
    filename = export_directory / "discovery with spaces.json"
    server = ControlServer(filename, qapp)
    server.publish_state('{"state":"initial"}')
    server.start()
    clients: list[QWebSocket] = []
    commands: list[str] = []
    senders: list[QWebSocket] = []

    def remember_sender(sender: QWebSocket, _message: str) -> None:
        senders.append(sender)

    server.received.connect(commands.append)
    server.command_received.connect(remember_sender)
    try:
        descriptor = json.loads(filename.read_text())
        assert descriptor["version"] == TRANSPORT_VERSION
        assert server.server.serverAddress().toString() == "127.0.0.1"
        assert descriptor["port"] == server.server.serverPort()
        with pytest.raises(RuntimeError, match="already listening"):
            server.start()

        for hello in [
            "not JSON",
            "{}",
            json.dumps({"version": TRANSPORT_VERSION + 1, "token": descriptor["token"]}),
            json.dumps({"version": True, "token": descriptor["token"]}),
            json.dumps({"version": TRANSPORT_VERSION, "token": "0" * 64}),
        ]:
            client = QWebSocket()
            clients.append(client)
            with qtbot.waitSignal(client.connected):
                client.open(QUrl(f"ws://127.0.0.1:{descriptor['port']}"))
            with qtbot.waitSignal(client.disconnected):
                client.sendTextMessage(hello)
        assert commands == []

        idle = QWebSocket()
        clients.append(idle)
        with qtbot.waitSignal(idle.connected):
            idle.open(QUrl(f"ws://127.0.0.1:{descriptor['port']}"))
        with qtbot.waitSignal(idle.disconnected, timeout=6000):
            pass  # No authentication: the server must enforce its deadline.
        assert commands == []

        binary = QWebSocket()
        clients.append(binary)
        with qtbot.waitSignal(binary.connected):
            binary.open(QUrl(f"ws://127.0.0.1:{descriptor['port']}"))
        with qtbot.waitSignal(binary.disconnected):
            binary.sendBinaryMessage(QByteArray(b"not a text command"))
        assert commands == []

        client = QWebSocket()
        clients.append(client)
        messages: list[str] = []
        client.textMessageReceived.connect(messages.append)
        with qtbot.waitSignal(client.connected):
            client.open(QUrl(f"ws://127.0.0.1:{descriptor['port']}"))
        client.sendTextMessage(
            json.dumps({"version": TRANSPORT_VERSION, "token": descriptor["token"]}),
        )
        qtbot.waitUntil(lambda: len(messages) == 2)
        assert json.loads(messages[0]) == {"transport": "ready", "version": TRANSPORT_VERSION}
        assert messages[1] == '{"state":"initial"}'
        client.sendTextMessage('{"command":"probe"}')
        qtbot.waitUntil(lambda: commands == ['{"command":"probe"}'])
        assert len(senders) == 1
        server.reply(client, '{"response":"must not reach an unauthenticated peer"}')
        with pytest.raises(ValueError, match="response exceeds"):
            server.reply(senders[0], "é" * (MAX_MESSAGE_BYTES // 2 + 1))
        server.reply(senders[0], '{"response":"confirmed"}')
        qtbot.waitUntil(lambda: messages[-1] == '{"response":"confirmed"}')
        assert commands == ['{"command":"probe"}']
        server.publish_state('{"state":"updated"}')
        qtbot.waitUntil(lambda: messages[-1] == '{"state":"updated"}')
        with pytest.raises(ValueError, match="message limit"):
            server.publish_state("x" * (MAX_MESSAGE_BYTES + 1))

        with qtbot.waitSignal(client.disconnected):
            client.sendTextMessage("x" * (MAX_MESSAGE_BYTES + 1))
        assert commands == ['{"command":"probe"}']

        # Shutdown must not delete a successor's discovery file.
        filename.write_text('{"successor":true}')
        server.close()
        assert filename.read_text() == '{"successor":true}'
    finally:
        for client in clients:
            client.abort()
        server.close()


def test_qt_rejects_browser_origins_and_failed_discovery(
    qapp: QApplication,
    qtbot: QtBot,
    export_directory: Path,
) -> None:
    server = ControlServer(export_directory / "endpoint.json", qapp)
    server.start()
    client = QWebSocket("https://example.invalid")
    try:
        with qtbot.waitSignal(client.disconnected):
            client.open(QUrl(f"ws://127.0.0.1:{server.server.serverPort()}"))
        assert client.state() == QAbstractSocket.SocketState.UnconnectedState
    finally:
        client.abort()
        server.close()
    assert not server.endpoint_path.exists()

    blocked = export_directory / "not-a-directory"
    blocked.write_text("file")
    broken = ControlServer(blocked / "endpoint.json", qapp)
    with pytest.raises(OSError):
        broken.start()
    assert not broken.server.isListening()
    broken.close()
