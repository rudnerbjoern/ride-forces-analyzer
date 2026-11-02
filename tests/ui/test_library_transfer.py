"""Settings owns ZIP backup/restore, confirmation, drafts and transfer cancellation."""

from pathlib import Path
from collections.abc import Callable
from threading import Event
from unittest.mock import Mock
from zipfile import is_zipfile

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QFileDialog, QMessageBox

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.storage.library_backup import LibraryBackup
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until


def test_settings_backup_restore_confirmation_and_cancel_keep_their_contracts(
    explorer_window: ExplorerWindow,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    source = synthetic_source(name="Saved ride")
    store = LibraryStore()
    store.archive(source, "saved.forces", (2, 6), CalibrationOverrides())
    store.update_metadata(source.source_sha256, {"ride_name": "Saved name", "notes": "Saved notes"})
    labels = ("YouTube", "Unused option")
    assert window.preferences.remember_library_video_labels(labels)
    window.library.toggle_button.click()
    window.settings_action.trigger()
    settings = window.findChild(SettingsDialog, "settingsDialog")
    assert settings is not None and settings.isVisible()
    transfer = settings.library_transfer
    assert transfer.backup_button.size() == transfer.restore_button.size()
    settings.library_labels.name.setText("Unsaved draft")
    path = export_directory / "library.zip"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", Mock(return_value=(str(path), "")))
    transfer.backup_button.click()
    wait_until(lambda: not transfer.busy)
    assert is_zipfile(path)
    assert settings.library_labels.name.text() == "Unsaved draft"
    assert "backup saved" in settings.library_error.text()
    store.update_metadata(source.source_sha256, {"ride_name": "Later name"})
    window.preferences.remember_library_video_labels(("Later option",))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", Mock(return_value=(str(path), "")))
    question = Mock(return_value=QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "question", question)
    transfer.restore_button.click()
    assert question.call_count == 1 and not transfer.busy
    assert store.entries()[0].ride_name == "Later name"
    question.return_value = QMessageBox.StandardButton.Yes
    transfer.restore_button.click()
    wait_until(lambda: not transfer.busy)
    assert "restored" in settings.library_error.text()
    assert store.entries()[0].ride_name == "Saved name"
    metadata = store.metadata(source.source_sha256)
    assert metadata is not None and metadata.notes == "Saved notes"
    assert Preferences().library_video_labels() == labels
    assert settings.library_labels.labels() == labels
    assert window.library.recordings.topLevelItemCount() == 1
    settings.grab().save(".tmp/lib13-settings-dark.png")
    window.set_ui_language(1)
    window.set_appearance(1)
    settings.grab().save(".tmp/lib13-settings-light.png")
    assert transfer.backup_button.text() != "Backup…"
    window.set_ui_language(0)
    previous = path.read_bytes()
    entered, release = Event(), Event()
    original = LibraryBackup.backup

    def delayed(
        self: LibraryBackup,
        destination: Path,
        *,
        overwrite: bool = False,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Path:
        entered.set()
        assert release.wait(5)
        return original(self, destination, overwrite=overwrite, cancelled=cancelled)

    monkeypatch.setattr(LibraryBackup, "backup", delayed)
    transfer.backup_button.click()
    wait_until(entered.is_set)
    try:
        assert not settings.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
        settings.reject()
        assert settings.isVisible() and transfer.busy
    finally:
        release.set()
    wait_until(lambda: not transfer.busy)
    assert "cancelled" in settings.library_error.text()
    assert path.read_bytes() == previous
    assert settings.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    settings.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    wait_until(lambda: window.findChild(SettingsDialog) is None)
    assert Preferences().library_video_labels() == labels
    assert store.entries()[0].ride_name == "Saved name"
