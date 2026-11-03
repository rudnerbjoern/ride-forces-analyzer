"""Real application Qt server and plugin TypeScript client interoperability."""

# cspell:words qapp qtbot pytestqt

import json
from pathlib import Path
from shutil import which

import pytest
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from ride_forces_analyzer.runtime.stream_deck import ControlServer


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
