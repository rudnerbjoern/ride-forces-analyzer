"""Native export-dialog interaction and background worker lifecycle."""

# cspell:words getpixel autouse

from pathlib import Path
from threading import Event
from tempfile import TemporaryDirectory
from collections.abc import Iterator

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QFileDialog, QInputDialog, QPushButton
import pytest

from ride_forces_analyzer.ui.export import ExportDialog, ExportWorker
from ride_forces_analyzer.ui.window import ExplorerWindow
from ride_forces_analyzer.rendering.preview import ExportPreview
from tests.ui.helpers import wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


pytestmark = pytest.mark.usefixtures("small_preview_frames")


@pytest.fixture(autouse=True)
def isolated_export_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from ride_forces_analyzer.ui import export as ui_export
    from ride_forces_analyzer.storage import exports as storage
    from ride_forces_analyzer.storage import preferences

    with TemporaryDirectory(dir=".tmp") as directory:
        path = Path(directory).resolve() / "exports.sqlite3"
        monkeypatch.setattr(ui_export, "default_database_path", lambda: path)
        monkeypatch.setattr(storage, "default_database_path", lambda: path)
        monkeypatch.setattr(preferences, "default_database_path", lambda: path)
        yield


def preview_ready(dialog: ExportDialog) -> ExportPreview:
    wait_until(lambda: dialog.preview_result is not None)
    result = dialog.preview_result
    assert result is not None
    return result


@pytest.mark.parametrize("configured", ["absolute", "relative", "directory", "missing", "empty"])
def test_ffmpeg_browse_starts_in_configured_folder_and_preserves_cancelled_path(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    preview_ready(dialog)
    browse = next(
        button for button in dialog.findChildren(QPushButton) if button.text() == "Browse…"
    )
    with TemporaryDirectory(dir=".tmp") as temporary:
        folder = Path(temporary).resolve() / "encoder folder"
        folder.mkdir()
        executable = folder / "ffmpeg.exe"
        if configured != "missing":
            executable.write_bytes(b"reference executable")
        original = (
            ""
            if configured == "empty"
            else str(folder)
            if configured == "directory"
            else str(executable.relative_to(Path.cwd()))
            if configured == "relative"
            else str(executable)
        )
        dialog.encoder.setText(original)
        starts: list[str] = []
        answer = [""]

        def choose(*args: object, **kwargs: object) -> tuple[str, str]:
            starts.append(str(args[2]))
            return answer[0], ""

        monkeypatch.setattr(QFileDialog, "getOpenFileName", choose)
        browse.click()
        assert starts[-1] == ("" if configured == "empty" else str(folder))
        assert dialog.encoder.text() == original
        other = folder / "other"
        other.mkdir()
        answer[0] = str(other / "ffmpeg.exe")
        browse.click()
        assert dialog.encoder.text() == answer[0]
        answer[0] = ""
        browse.click()
        assert starts[-1] == str(other)
        assert dialog.encoder.text() == str(other / "ffmpeg.exe")


def test_save_dialog_suggests_source_name_and_restores_successful_export_folder(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui import export as ui_export
    from ride_forces_analyzer.storage.preferences import Preferences

    window = explorer_window
    source = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    window.open_path(source)
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    preview_ready(dialog)
    dialog.next.click()
    with TemporaryDirectory(dir=".tmp") as temporary:
        output = Path(temporary).resolve() / "custom.mov"
        suggestions: list[str] = []

        def destination(*args: object, **kwargs: object) -> tuple[str, str]:
            suggestions.append(str(args[2]))
            return (str(output), "") if len(suggestions) == 1 else ("", "")

        monkeypatch.setattr(QFileDialog, "getSaveFileName", destination)

        def encoder(path: Path | None = None) -> Path:
            return Path(__file__)

        def export(*args: object, **kwargs: object) -> Path:
            return output

        monkeypatch.setattr(ui_export, "find_ffmpeg", encoder)
        monkeypatch.setattr(ui_export, "export_video", export)
        dialog.start.click()
        wait_until(lambda: dialog.worker is None)
        assert Path(suggestions[0]).name == source.stem + ".mov"
        assert Preferences(dialog.preferences.path).export_directory() == str(output.parent)
        dialog.start.click()
        assert Path(suggestions[1]) == output.parent / (source.stem + ".mov")
        assert dialog.preferences.export_directory() == str(output.parent)
    dialog.close()


def test_portrait_format_refreshes_all_previews_and_review(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    preview_ready(dialog)
    estimate = dialog.size_estimate.text()
    assert "Estimated file size:" in estimate and "MiB" in estimate
    dialog.mode.setCurrentIndex(1)
    assert dialog.size_estimate.text() != estimate
    assert dialog.review_size_estimate.text() == dialog.size_estimate.text()
    dialog.mode.setCurrentIndex(0)
    assert dialog.size_estimate.text() == estimate
    dialog.aspect.setCurrentIndex(1)
    wait_until(lambda: dialog.preview_result is None)
    result = preview_ready(dialog)
    assert all(profile.image.size == (540, 960) for profile in result.profiles)

    def preset_name(*args: object, **kwargs: object) -> tuple[str, bool]:
        return "Portrait", True

    monkeypatch.setattr(QInputDialog, "getText", preset_name)
    dialog.save_preset.click()
    assert dialog.store.presets()[0].settings.aspect == "portrait"
    dialog.aspect.setCurrentIndex(0)
    dialog.load_preset.click()
    assert dialog.aspect.currentIndex() == 1
    preview_ready(dialog)
    dialog.next.click()
    assert "2160×3840" in dialog.summary.text()
    dialog.close()


def test_export_dialog_tracks_loaded_source_and_range(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    assert not window.export_button.isEnabled()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.export_button.isEnabled()
    window.first.setValue(120)
    window.last.setValue(160)
    assert window.data is not None
    sample = window.data.source.recording.indices.start + 72 * 50
    window.slider.setValue(sample)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog) and dialog.isVisible()
    assert (dialog.first, dialog.last) == (120, 160)
    assert "Manta" in dialog.windowTitle()
    assert dialog.mode.currentIndex() == 0 and dialog.fps.currentText() == "50"
    assert dialog.layout_profile.count() == 5
    assert dialog.layout_profile.currentIndex() == 0
    assert dialog.current_sample == sample
    wait_until(lambda: dialog.preview_result is not None)
    assert dialog.preview_result is not None and dialog.preview_result.sample == sample
    assert all(not button.icon().isNull() for button in dialog.profile_buttons)
    assert dialog.preview_caption.height() >= 2 * dialog.preview_caption.fontMetrics().height()
    dialog.profile_buttons[0].click()
    assert dialog.profile_buttons[0].isChecked()
    assert dialog.pages.currentIndex() == 0 and not dialog.start.isVisible()
    assert dialog.flip_vertical.isChecked() and not dialog.flip_lateral.isChecked()
    wait_until(lambda: dialog.preview_result is not None)
    dialog.interval.setCurrentIndex(1)
    wait_until(lambda: dialog.preview_result is not None)
    assert dialog.preview_result is not None and dialog.preview_result.outside_range
    assert dialog.preview_result.sample == sample
    assert "OUTSIDE" in dialog.preview_note.text()
    dialog.next.click()
    assert dialog.pages.currentIndex() == 1 and dialog.start.isVisible()
    assert f"{sample:,}" in dialog.summary.text()
    dialog.back.click()
    assert dialog.pages.currentIndex() == 0
    dialog.layout_profile.setCurrentIndex(4)
    assert dialog.flip_vertical.isChecked() and not dialog.flip_lateral.isChecked()
    dialog.layout_profile.setCurrentIndex(3)
    assert dialog.flip_vertical.isEnabled() and not dialog.flip_lateral.isEnabled()
    assert dialog.flip_vertical.isChecked()
    dialog.layout_profile.setCurrentIndex(0)
    assert dialog.flip_vertical.isEnabled() and not dialog.flip_lateral.isEnabled()
    assert dialog.flip_vertical.isChecked() and not dialog.flip_lateral.isChecked()
    dialog.close()


def test_export_worker_progress_cancel_and_gui_recovery(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui import export as ui_export
    from ride_forces_analyzer.rendering.encoding import ExportCancelled

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    dialog.layout_profile.setCurrentIndex(3)
    wait_until(lambda: dialog.preview_result is not None)
    dialog.next.click()
    started = Event()
    clock = 0.0
    monkeypatch.setattr(ui_export, "monotonic", lambda: clock)

    def fake_export(*args: object, **kwargs: object) -> Path:
        from ride_forces_analyzer.rendering.model import ExportTimeline

        assert isinstance(args[0], ExportTimeline)
        assert args[0].settings.layout == "orbit"
        started.set()
        cancelled = kwargs["cancelled"]
        assert isinstance(cancelled, Event)
        if not cancelled.wait(5):
            raise RuntimeError("Test cancellation was not delivered")
        raise ExportCancelled()

    monkeypatch.setattr(ui_export, "export_video", fake_export)

    def encoder(_: Path | None = None) -> Path:
        return Path(__file__)

    def destination(*args: object, **kwargs: object) -> tuple[str, str]:
        return "unused.mov", ""

    monkeypatch.setattr(ui_export, "find_ffmpeg", encoder)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", destination)
    dialog.start.click()
    wait_until(started.is_set)
    assert isinstance(dialog.worker, ExportWorker)
    assert not dialog.start.isEnabled()
    clock = 10.0
    dialog.worker.signals.progress.emit(100, 1000)
    wait_until(lambda: dialog.progress.value() == 10)
    assert dialog.eta_timer.interval() == 2000
    wait_until(lambda: "1:30" in dialog.eta.text())
    dialog.worker.signals.progress.emit(1000, 1000)
    wait_until(lambda: dialog.eta.text() == "Frames complete · finalizing video…")
    dialog.reject()
    assert dialog.isVisible()
    assert not window.close()  # A close requests cancellation, never abandons a live worker.
    wait_until(lambda: dialog.worker is None)
    QThreadPool.globalInstance().waitForDone()
    assert dialog.start.isEnabled()
    assert "cancelled" in dialog.status.text()
    assert not dialog.eta_timer.isActive() and dialog.eta.text() == ""
    dialog.close()


def test_preview_refreshes_settings_without_encoding(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    wait_until(lambda: dialog.preview_result is not None)
    sample = dialog.current_sample
    dialog.profile_buttons[3].click()
    dialog.fps.setCurrentText("30")
    dialog.seconds.setValue(8)
    dialog.background.setCurrentIndex(2)
    assert dialog.preview_result is None and not dialog.next.isEnabled()
    dark_preview = preview_ready(dialog)
    assert dialog.current_sample == sample and "G-Orbit" in dialog.preview_caption.text()
    assert dark_preview.profiles[3].image.getpixel((0, 0)) == (22, 37, 51)
    dialog.mode.setCurrentIndex(1)
    opaque_preview = preview_ready(dialog)
    assert all(profile.image.getpixel((0, 0)) == (0, 0, 0) for profile in opaque_preview.profiles)
    assert dialog.worker is None
    dialog.close()


def test_stale_preview_is_discarded_after_fast_profile_changes(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui import export as ui_export
    from ride_forces_analyzer.explorer import ExplorerData
    from ride_forces_analyzer.rendering.model import ExportSettings

    original = ui_export.build_previews
    started, release = Event(), Event()
    calls: list[tuple[str, int | str]] = []

    def delayed(
        data: ExplorerData,
        settings: ExportSettings,
        first: int,
        last: int,
        sample: int,
        background: str,
    ) -> ExportPreview:
        calls.append((settings.layout, settings.fps))
        if len(calls) == 1:
            started.set()
            if not release.wait(8):
                raise RuntimeError("Preview test was not released")
        return original(
            data,
            settings,
            first,
            last,
            sample,
            "dark" if background == "dark" else "checker",
        )

    monkeypatch.setattr(ui_export, "build_previews", delayed)
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    try:
        wait_until(started.is_set)
        dialog.layout_profile.setCurrentIndex(3)
        dialog.fps.setCurrentText("30")
        assert dialog.preview_result is None and not dialog.next.isEnabled()
    finally:
        release.set()
    wait_until(lambda: dialog.preview_result is not None)
    assert calls == [("ribbon", 50), ("orbit", 30)]
    assert "G-Orbit" in dialog.preview_caption.text()
    assert dialog.next.isEnabled() and dialog.worker is None
    dialog.reject()
    assert dialog.closing and not dialog.isVisible()


def test_saved_presets_and_recording_queue_survive_assistant_reopen(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui.batches import BatchDialog

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    names = ["Orbit5994", "Ribbon50"]

    def name_dialog(*args: object, **kwargs: object) -> tuple[str, bool]:
        return names.pop(0), True

    def batch_dialog(*args: object, **kwargs: object) -> tuple[str, bool]:
        return "Weekend", True

    monkeypatch.setattr(QInputDialog, "getText", name_dialog)
    monkeypatch.setattr(QInputDialog, "getItem", batch_dialog)
    dialog.layout_profile.setCurrentIndex(3)
    dialog.fps.setCurrentText("59.94")
    dialog.smoothing.setCurrentIndex(1)
    dialog.seconds.setValue(12.5)
    dialog.interval.setCurrentIndex(2)
    dialog.save_preset.click()
    dialog.queue.click()
    dialog.layout_profile.setCurrentIndex(0)
    dialog.fps.setCurrentText("50")
    dialog.smoothing.setCurrentIndex(5)
    dialog.save_preset.click()
    dialog.queue.click()
    saved = dialog.store.batch("Weekend")
    assert len(saved.jobs) == 2
    assert saved.jobs[0].preset.settings.layout == "orbit"
    assert saved.jobs[0].preset.settings.fps == "60000/1001"
    assert saved.jobs[0].preset.smoothing_window == 3
    assert saved.jobs[1].preset.settings.layout == "ribbon"
    dialog.fps.setCurrentText("25")
    dialog.update_preset.click()
    assert dialog.store.batch("Weekend").jobs[1].preset.settings.fps == 50
    dialog.close()
    window.export_button.click()
    reopened = window.export_window
    assert isinstance(reopened, ExportDialog)
    assert reopened.preset_selector.count() == 3
    reopened.preset_selector.setCurrentText("Orbit5994")
    reopened.load_preset.click()
    preview_ready(reopened)
    assert reopened.layout_profile.currentIndex() == 3
    assert reopened.fps.currentText() == "59.94" and reopened.seconds.value() == 12.5
    assert reopened.smoothing.currentIndex() == 1 and reopened.interval.currentIndex() == 2
    assert "3 samples" in reopened.preview_caption.text()
    assert window.data is not None and window.data.reference is not None
    assert window.data.reference.smoothing_window == 11
    reopened.manage_batches.click()
    assert isinstance(reopened.batch_window, BatchDialog)
    assert reopened.batch_window.table.rowCount() == 2
    reopened.close()


def test_batch_editor_multi_ride_presets_and_run_all_cancellation(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui import batches as ui_batches
    from ride_forces_analyzer.storage.exports import ExportStore, default_database_path
    from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset
    from ride_forces_analyzer.rendering.model import ExportSettings
    from ride_forces_analyzer.rendering.batches import BatchReport, JobResult

    store = ExportStore(default_database_path())
    store.save_preset(SavedPreset(name="Ribbon", settings=ExportSettings(layout="ribbon")))
    store.save_preset(SavedPreset(name="Orbit", settings=ExportSettings(layout="orbit")))
    store.create_batch("Day1")
    window = explorer_window
    assert window.data is None and window.batches_button.isEnabled()
    window.batches_button.click()
    dialog = window.batch_window
    assert isinstance(dialog, ui_batches.BatchDialog)
    dialog.presets.selectAll()

    def files(*args: object, **kwargs: object) -> tuple[list[str], str]:
        return [
            str(next(REAL_FIXTURE_DIRECTORY.glob(f"{ride}-*.forces")))
            for ride in ("Manta", "Kraken")
        ], ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", files)
    dialog.add.click()
    wait_until(lambda: dialog.builder is None)
    assert dialog.table.rowCount() == 4
    assert len(store.batch("Day1").jobs) == 4
    store.save_batch(SavedBatch(name="Day2", jobs=store.batch("Day1").jobs[:1]))
    dialog.refresh("Day1")
    started = Event()
    names: list[str] = []

    def fake_run(batches: tuple[SavedBatch, ...], directory: Path, **kwargs: object) -> BatchReport:
        names.extend(batch.name for batch in batches)
        started.set()
        cancelled = kwargs["cancelled"]
        assert isinstance(cancelled, Event) and cancelled.wait(5)
        return BatchReport(
            directory=directory,
            results=tuple(
                JobResult(
                    batch=batch.name,
                    job=index,
                    ride=job.ride,
                    preset=job.preset.name,
                    status="cancelled",
                )
                for batch in batches
                for index, job in enumerate(batch.jobs, 1)
            ),
        )

    def folder(*args: object, **kwargs: object) -> str:
        return str(store.path.parent)

    def encoder(_: Path | None = None) -> Path:
        return Path(__file__)

    monkeypatch.setattr(ui_batches, "run_batches", fake_run)
    monkeypatch.setattr(ui_batches, "find_ffmpeg", encoder)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", folder)
    dialog.run_all.click()
    wait_until(started.is_set)
    assert names == ["Day1", "Day2"]
    assert dialog.worker is not None
    dialog.worker.signals.progress.emit(1, 5, 1, 2, "Day1 · Manta · Orbit")
    wait_until(lambda: dialog.progress.value() == 10)
    assert "Manta" in dialog.current_job.text()
    assert not window.close()
    wait_until(lambda: dialog.worker is None)
    assert dialog.last_report is not None and len(dialog.last_report.results) == 5
    assert "5 cancelled" in dialog.status.text()
    assert len(store.batch("Day1").jobs) == 4
    dialog.table.selectAll()
    dialog.remove.click()
    assert store.batch("Day1").jobs == ()
    dialog.delete.click()
    assert [batch.name for batch in store.batches()] == ["Day2"]
    dialog.close()
