"""Export transport and storage failures recover without visible desktop windows."""

# cspell:words qapp

from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QWidget

from ride_forces_analyzer.explorer import present_recording
from ride_forces_analyzer.rendering.model import ExportSettings
from ride_forces_analyzer.rendering.preview import ExportPreview, PreviewBackground
from ride_forces_analyzer.storage.export_models import BatchJob, make_preset
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.exports.batches import BatchDialog
from ride_forces_analyzer.ui.exports.form import ExportForm
from ride_forces_analyzer.ui.exports.presets import ExportPresets
from ride_forces_analyzer.ui.exports.preview_controller import PreviewController
from ride_forces_analyzer.ui.exports.workers import PreviewWorker
from tests.exports.test_csv_export import snapshot


def test_preview_failures_respect_revision_and_shutdown(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = QWidget()
    controller = PreviewController(parent)
    analysis = snapshot()
    ready: list[object] = []
    failed: list[str] = []
    workers: list[PreviewWorker] = []
    controller.ready.connect(ready.append)
    controller.failed.connect(failed.append)
    monkeypatch.setattr(QThreadPool, "start", Mock(side_effect=workers.append))
    build = Mock(side_effect=RuntimeError("Preview failed"))
    monkeypatch.setattr("ride_forces_analyzer.ui.exports.workers.build_previews", build)

    def schedule() -> PreviewWorker:
        controller.schedule(analysis, ExportSettings(), 0, 0, 0, PreviewBackground.CHECKER, {})
        controller.timer.stop()
        controller.timer.timeout.emit()
        return workers[-1]

    try:
        old = schedule()
        assert schedule() is old  # A new intent waits for the active worker.
        old.run()
        assert failed == [] and len(workers) == 2
        assert controller.worker is workers[-1]
        workers[-1].run()
        assert failed == ["Preview failed"] and controller.worker is None

        result = ExportPreview(0, False, ())
        build.side_effect = None
        build.return_value = result
        schedule().run()
        assert ready == [result] and controller.result is result

        late = schedule()
        QTimer.singleShot(0, late.run)
        QTimer.singleShot(0, lambda: late.signals.failed.emit(late.revision, "Late failure"))
        controller.close()
        qapp.processEvents()
        assert ready == [result] and failed == ["Preview failed"]
        assert controller.result is None and controller.worker is None
        assert not controller.timer.isActive()
    finally:
        controller.close()
        parent.deleteLater()


def test_preset_storage_errors_preserve_definitions_and_allow_retry(
    qapp: QApplication,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = snapshot()
    parent = QWidget()
    store = ExportStore(export_directory / "exports.sqlite3")
    preset = make_preset("Existing", ExportSettings(), 3, "markers", analysis.configuration)
    store.save_preset(preset)
    store.create_batch("Queue")
    form = ExportForm(present_recording(analysis.source, analysis=analysis), Preferences(), parent)
    controls = ExportPresets(store, form, analysis, 0, 0, parent)
    messages: list[object] = []
    controls.message.connect(messages.append)
    controls.refresh(preset.name)
    monkeypatch.setattr(QInputDialog, "getText", Mock(return_value=("New", True)))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(store, "presets", Mock(side_effect=ExportStoreError("List unavailable")))
            controls.refresh()
            assert str(messages[-1]) == "List unavailable"
            assert controls.preset_selector.currentText() == preset.name
        with monkeypatch.context() as patch:
            patch.setattr(store, "save_preset", Mock(side_effect=ExportStoreError("Save denied")))
            for button in (controls.save_preset, controls.update_preset):
                button.click()
                assert str(messages[-1]) == "Save denied" and button.isEnabled()
            assert store.presets() == (preset,)
        job = BatchJob(
            recording_path=(export_directory / "source.forces").resolve(),
            source_sha256=analysis.source.source_sha256,
            ride="Synthetic",
            preset=preset,
            range_mode="markers",
            first_sample=0,
            last_sample=0,
        )
        monkeypatch.setattr(
            "ride_forces_analyzer.ui.exports.presets.make_job",
            Mock(return_value=job),
        )
        monkeypatch.setattr(QInputDialog, "getItem", Mock(return_value=("Queue", True)))
        with monkeypatch.context() as patch:
            patch.setattr(store, "append_jobs", Mock(side_effect=ExportStoreError("Queue denied")))
            controls.queue.click()
            assert str(messages[-1]) == "Queue denied" and not store.batch("Queue").jobs
        controls.queue.click()
        assert store.batch("Queue").jobs == (job,)
        controls.save_preset.click()
        assert {saved.name for saved in store.presets()} == {"Existing", "New"}
        assert "Saved preset" in str(messages[-1])
    finally:
        parent.deleteLater()


def test_batch_storage_errors_keep_selection_and_allow_retry(
    qapp: QApplication,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = QWidget()
    store = ExportStore(export_directory / "batches.sqlite3")
    store.create_batch("Existing")
    dialog = BatchDialog(store, parent)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(store, "batches", Mock(side_effect=ExportStoreError("List unavailable")))
            dialog.refresh()
            assert dialog.status.text() == "List unavailable"
            assert dialog.batch_list.currentItem().text() == "Existing"
        monkeypatch.setattr(QInputDialog, "getText", Mock(return_value=("New", True)))
        with monkeypatch.context() as patch:
            patch.setattr(
                store,
                "create_batch",
                Mock(side_effect=ExportStoreError("Create denied")),
            )
            dialog.new.click()
            assert dialog.status.text() == "Create denied"
            assert [batch.name for batch in store.batches()] == ["Existing"]
        with monkeypatch.context() as patch:
            patch.setattr(
                store,
                "delete_batch",
                Mock(side_effect=ExportStoreError("Delete denied")),
            )
            dialog.delete.click()
            assert dialog.status.text() == "Delete denied"
            assert store.batch("Existing").name == "Existing"
        dialog.new.click()
        assert dialog.batch_list.currentItem().text() == "New"
        dialog.delete.click()
        assert [batch.name for batch in store.batches()] == ["Existing"]
        assert dialog.new.isEnabled() and dialog.delete.isEnabled()
    finally:
        dialog.close()
        parent.deleteLater()
