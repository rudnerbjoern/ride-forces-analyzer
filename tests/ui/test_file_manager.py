"""Native file reveal preserves filenames and falls back only without selection support."""

# cspell:words dbus

from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.ui.presentation import file_manager


def test_native_file_reveal_commands_and_missing_file(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filename = export_directory / "Bahn ü, final.mp4"
    filename.write_bytes(b"external video")
    filename = filename.resolve()
    launch = Mock()
    run = Mock()
    monkeypatch.setattr(file_manager.subprocess, "Popen", launch)
    monkeypatch.setattr(file_manager.subprocess, "run", run)
    with monkeypatch.context() as patch:
        patch.setattr(file_manager.sys, "platform", "win32")
        file_manager.show_in_folder(str(filename))
        launch.assert_called_once_with(f'explorer.exe /select,"{filename}"')
        run.assert_not_called()
    with monkeypatch.context() as patch:
        patch.setattr(file_manager.sys, "platform", "darwin")
        file_manager.show_in_folder(str(filename))
        run.assert_called_once_with(["open", "-R", str(filename)], check=True, capture_output=True)
    run.reset_mock()
    with monkeypatch.context() as patch:
        patch.setattr(file_manager.sys, "platform", "linux")
        file_manager.show_in_folder(str(filename))
        assert f"array:string:{filename.as_uri()}" in run.call_args.args[0]
        assert "org.freedesktop.FileManager1.ShowItems" in run.call_args.args[0]
        run.side_effect = subprocess.CalledProcessError(1, "dbus-send")
        opened = Mock(return_value=True)
        patch.setattr(file_manager.QDesktopServices, "openUrl", opened)
        file_manager.show_in_folder(str(filename))
        assert Path(opened.call_args.args[0].toLocalFile()) == filename.parent
        opened.return_value = False
        with pytest.raises(OSError, match="containing folder"):
            file_manager.show_in_folder(str(filename))
    launch.reset_mock()
    run.reset_mock()
    filename.unlink()
    with pytest.raises(FileNotFoundError):
        file_manager.show_in_folder(str(filename))
    launch.assert_not_called()
    run.assert_not_called()
