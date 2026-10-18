"""File-dialog preferences update only after a successful import."""

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtWidgets import QFileDialog
import pytest

from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.ui.helpers import wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_choose_file_remembers_success_but_not_failure_or_cancel(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        database = Path(temporary) / "preferences.sqlite3"
        window = explorer_window
        window.preferences = Preferences(database)
        recording = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")).resolve()
        selected = str(recording)
        directories: list[str] = []

        def choose(parent: object, title: str, directory: str, filters: str) -> tuple[str, str]:
            directories.append(directory)
            return selected, ""

        monkeypatch.setattr(QFileDialog, "getOpenFileName", choose)
        window.choose_file()
        wait_until(window.open_action.isEnabled)
        assert directories == [""]
        assert Preferences(database).recording_directory() == str(recording.parent)
        selected = str(Path(temporary) / "missing.forces")
        window.choose_file()
        wait_until(window.open_action.isEnabled)
        assert window.preferences.recording_directory() == str(recording.parent)
        selected = ""
        window.choose_file()
        assert directories[-2:] == [str(recording.parent)] * 2
        assert Preferences(database).recording_directory() == str(recording.parent)
