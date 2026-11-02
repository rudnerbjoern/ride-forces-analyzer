"""Native Qt transport, access checks and real TypeScript-client interoperability."""

# cspell:words qapp qtbot pytestqt

import json
from pathlib import Path
from shutil import which

import pytest
from PySide6.QtCore import QByteArray, QProcess, QTimer, QUrl
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from ride_forces_analyzer.runtime.stream_deck import ControlServer, MAX_MESSAGE_BYTES


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
    server.received.connect(commands.append)
    try:
        descriptor = json.loads(filename.read_text())
        assert descriptor["version"] == 1
        assert server.server.serverAddress().toString() == "127.0.0.1"
        assert descriptor["port"] == server.server.serverPort()
        with pytest.raises(RuntimeError, match="already listening"):
            server.start()

        for hello in [
            "not JSON",
            "{}",
            json.dumps({"version": 2, "token": descriptor["token"]}),
            json.dumps({"version": True, "token": descriptor["token"]}),
            json.dumps({"version": 1, "token": "0" * 64}),
        ]:
            client = QWebSocket()
            clients.append(client)
            with qtbot.waitSignal(client.connected):
                client.open(QUrl(f"ws://127.0.0.1:{descriptor['port']}"))
            with qtbot.waitSignal(client.disconnected):
                client.sendTextMessage(hello)
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
        client.sendTextMessage(json.dumps({"version": 1, "token": descriptor["token"]}))
        qtbot.waitUntil(lambda: len(messages) == 2)
        assert json.loads(messages[0]) == {"transport": "ready", "version": 1}
        assert messages[1] == '{"state":"initial"}'
        client.sendTextMessage('{"command":"probe"}')
        qtbot.waitUntil(lambda: commands == ['{"command":"probe"}'])
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


def test_real_node_client_discovers_qt_and_reconnects_after_restart(
    qapp: QApplication,
    qtbot: QtBot,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(export_directory.resolve()))
    node = which("node")
    assert node is not None, "Node.js is required for the transport interoperability test"
    server = ControlServer(parent=qapp)
    server.publish_state('{"phase":"initial"}')
    server.start()
    original = json.loads(server.endpoint_path.read_text())
    commands: list[str] = []

    def restart() -> None:
        server.publish_state('{"phase":"restarted"}')
        server.start()

    def received(message: str) -> None:
        commands.append(message)
        if json.loads(message)["command"] == "restart":
            server.close()
            QTimer.singleShot(50, restart)
        else:
            server.publish_state('{"phase":"complete"}')

    server.received.connect(received)
    process = QProcess()
    process.setProgram(node)
    process.setArguments([str(Path(__file__).with_name("stream_deck_client.mjs").resolve())])
    try:
        process.start()
        qtbot.waitUntil(lambda: process.state() == QProcess.ProcessState.NotRunning, timeout=15000)
        output = bytes(process.readAllStandardOutput().data()).decode()
        errors = bytes(process.readAllStandardError().data()).decode()
        assert process.exitCode() == 0, output + errors
        assert json.loads(output) == {"connections": [True, False, True, False]}
        assert [json.loads(command)["command"] for command in commands] == ["restart", "complete"]
        assert json.loads(server.endpoint_path.read_text())["token"] != original["token"]
    finally:
        process.kill()
        process.waitForFinished(1000)
        server.close()
    assert not server.endpoint_path.exists()
