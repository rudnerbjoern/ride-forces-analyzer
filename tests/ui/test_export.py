"""Native export-dialog interaction and background worker lifecycle."""

from ride_forces_analyzer.rendering.model import StandardFrameRate

from ride_forces_analyzer.rendering.model import ExportLayout, VideoAspect
from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress
from ride_forces_analyzer.analysis.preparation import (
    source_app_configuration,
)

# cspell:words getpixel

from pathlib import Path
from threading import Event
from tempfile import TemporaryDirectory

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QFileDialog, QInputDialog, QPushButton
import pytest

from ride_forces_analyzer.ui.exports.video import ExportDialog
from ride_forces_analyzer.ui.exports.workers import ExportWorker
from ride_forces_analyzer.ui.exports import workers as ui_workers
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.rendering.preview import ExportPreview, PreviewBackground
from tests.ui.helpers import wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


pytestmark = pytest.mark.usefixtures("small_preview_frames")


def preview_ready(dialog: ExportDialog) -> ExportPreview:
    wait_until(lambda: dialog.previews.result is not None)
    result = dialog.previews.result
    assert result is not None
    return result


def test_export_source_range_layout_preview_and_portrait_preset_workflow(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    assert not window.export_button.isEnabled()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.export_button.isEnabled()
    window.inspector.first.setValue(120)
    window.inspector.last.setValue(160)
    assert window.data is not None
    sample = window.data.source.recording.indices.start + 72 * 50
    window.navigation.slider.setValue(sample)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog) and dialog.isVisible()
    assert (dialog.first, dialog.last) == (120, 160)
    assert "Manta" in dialog.windowTitle()
    assert dialog.form.mode.currentIndex() == 0 and dialog.form.fps.currentText() == "50"
    assert dialog.form.layout_profile.count() == 5
    assert dialog.form.layout_profile.currentIndex() == 0
    assert dialog.current_sample == sample
    wait_until(lambda dialog=dialog: dialog.previews.result is not None)
    assert dialog.previews.result is not None and dialog.previews.result.sample == sample
    assert all(not button.icon().isNull() for button in dialog.profile_buttons)
    assert dialog.preview_caption.height() >= dialog.preview_caption.fontMetrics().height()
    dialog.profile_buttons[0].click()
    assert dialog.profile_buttons[0].isChecked()
    assert dialog.pages.currentIndex() == 0 and not dialog.start.isVisible()
    assert dialog.form.flip_vertical.isChecked() and not dialog.form.flip_lateral.isChecked()
    wait_until(lambda dialog=dialog: dialog.previews.result is not None)
    dialog.form.interval.setCurrentIndex(1)
    wait_until(lambda dialog=dialog: dialog.previews.result is not None)
    assert dialog.previews.result is not None and dialog.previews.result.outside_range
    assert dialog.previews.result.sample == sample
    assert "OUTSIDE" in dialog.preview_note.text()
    dialog.next.click()
    assert dialog.pages.currentIndex() == 1 and dialog.start.isVisible()
    assert f"{sample:,}" in dialog.preview_caption.text()
    assert dialog.review_fields["layout"].text() == "Flow Ribbon"
    assert dialog.review_fields["samples"].text() == "120–160 (inclusive)"
    assert not dialog.presets.isVisible() and not dialog.gallery.isVisible()
    assert dialog.preview_note.isVisible()  # The out-of-range warning remains visible.
    dialog.back.click()
    assert dialog.pages.currentIndex() == 0
    assert dialog.presets.isVisible() and dialog.gallery.isVisible()
    dialog.form.layout_profile.setCurrentIndex(4)
    assert dialog.form.flip_vertical.isChecked() and not dialog.form.flip_lateral.isChecked()
    dialog.form.layout_profile.setCurrentIndex(3)
    assert dialog.form.flip_vertical.isEnabled() and not dialog.form.flip_lateral.isEnabled()
    assert dialog.form.flip_vertical.isChecked()
    dialog.form.layout_profile.setCurrentIndex(0)
    assert dialog.form.flip_vertical.isEnabled() and not dialog.form.flip_lateral.isEnabled()
    assert dialog.form.flip_vertical.isChecked() and not dialog.form.flip_lateral.isChecked()
    dialog.close()

    # Check layout/position transitions in the same Explorer session.
    from dataclasses import replace

    from ride_forces_analyzer.rendering.layouts import registry
    from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition, LayoutPositions
    from ride_forces_analyzer.rendering.model import PROFILES

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    preview_ready(dialog)
    analysis = dialog.analysis

    def choose_layout(key: str) -> None:
        dialog.form.layout_profile.setCurrentIndex(
            next(i for i, (name, _) in enumerate(PROFILES) if name == key),
        )

    def choices() -> list[str]:
        return [dialog.form.position.itemData(i) for i in range(dialog.form.position.count())]

    assert choices() == ["top", "bottom"]
    assert dialog.form.position.currentData() == LayoutPosition.BOTTOM
    dialog.form.position.setCurrentIndex(dialog.form.position.findData("top"))
    assert dialog.previews.result is None
    assert dialog.form.position.currentData() == LayoutPosition.TOP
    choose_layout(ExportLayout.HUD)
    assert choices() == ["full_screen"]
    assert dialog.form.position.currentData() == LayoutPosition.FULL_SCREEN
    assert dialog.form.seconds.value() == 30
    dialog.form.seconds.setValue(20)
    assert dialog.form.seconds.value() == 20
    choose_layout(ExportLayout.COLUMN)
    assert choices() == ["left", "right"]
    assert dialog.form.position.currentData() == LayoutPosition.RIGHT
    dialog.form.position.setCurrentIndex(dialog.form.position.findData("left"))
    choose_layout(ExportLayout.RIBBON)
    assert dialog.form.positions[ExportLayout.COLUMN] is LayoutPosition.LEFT
    choose_layout(ExportLayout.COLUMN)
    assert dialog.form.position.currentData() == LayoutPosition.LEFT
    dialog.form.position.setCurrentIndex(dialog.form.position.findData("right"))
    choose_layout(ExportLayout.ORBIT)
    assert set(choices()) == {"top_left", "top_right", "bottom_left", "bottom_right"}
    assert dialog.form.position.currentData() == LayoutPosition.TOP_RIGHT
    dialog.form.position.setCurrentIndex(dialog.form.position.findData("top_right"))
    choose_layout(ExportLayout.CORNERS)
    assert dialog.form.position.currentData() == LayoutPosition.TOP_RIGHT
    choose_layout(ExportLayout.RIBBON)
    dialog.form.position.setCurrentIndex(dialog.form.position.findData("bottom"))
    assert dialog.form.positions[ExportLayout.ORBIT] is LayoutPosition.BOTTOM_RIGHT
    assert dialog.form.positions[ExportLayout.CORNERS] is LayoutPosition.BOTTOM_RIGHT
    choose_layout(ExportLayout.ORBIT)
    assert dialog.form.position.currentData() == LayoutPosition.BOTTOM_RIGHT
    dialog.form.position.setCurrentIndex(dialog.form.position.findData("top_right"))
    choose_layout(ExportLayout.CORNERS)
    dialog.form.aspect.setCurrentIndex(1)
    assert dialog.form.position.currentData() == LayoutPosition.TOP_RIGHT

    original_plugins = registry.PLUGINS
    plugin = registry.PLUGINS[ExportLayout.CORNERS]
    portrait = LayoutPositions(
        regions={LayoutPosition.BOTTOM_LEFT: plugin.portrait.regions[LayoutPosition.BOTTOM_LEFT]},
        default=LayoutPosition.BOTTOM_LEFT,
    )
    monkeypatch.setattr(
        registry,
        "PLUGINS",
        {**registry.PLUGINS, ExportLayout.CORNERS: replace(plugin, portrait=portrait)},
    )
    dialog.form.aspect.setCurrentIndex(0)
    dialog.form.aspect.setCurrentIndex(1)
    assert choices() == ["bottom_left"]
    assert dialog.form.position.currentData() == LayoutPosition.BOTTOM_LEFT
    dialog.previews.timer.stop()
    dialog.previews.timer.timeout.emit()
    assert dialog.previews.worker is not None
    assert dialog.previews.worker.settings.position is LayoutPosition.BOTTOM_LEFT
    preview_ready(dialog)
    assert dialog.analysis is analysis
    assert dialog.form.position in dialog.controls

    monkeypatch.setattr(registry, "PLUGINS", original_plugins)
    dialog.form.aspect.setCurrentIndex(0)
    preview_ready(dialog)

    # Keep the same assistant for preview settings and portrait preset loading.
    sample = dialog.current_sample
    dialog.profile_buttons[3].click()
    dialog.form.fps.setCurrentText("30")
    dialog.form.seconds.setValue(8)
    dialog.background.setCurrentIndex(2)
    assert dialog.previews.result is None and not dialog.next.isEnabled()
    dark_preview = preview_ready(dialog)
    assert dialog.current_sample == sample and dialog.form.layout_profile.currentText() == "G-Orbit"
    assert dark_preview.profiles[3].image.getpixel((0, 0)) == (22, 37, 51)
    dialog.form.mode.setCurrentIndex(1)
    opaque_preview = preview_ready(dialog)
    assert all(profile.image.getpixel((0, 0)) == (0, 0, 0) for profile in opaque_preview.profiles)
    assert dialog.worker is None
    dialog.form.mode.setCurrentIndex(0)
    estimate = dialog.form.size_estimate.text()
    assert estimate.endswith(" MiB")
    assert estimate == dialog.review_size_estimate.text()
    dialog.form.mode.setCurrentIndex(1)
    assert dialog.form.size_estimate.text() != estimate
    assert dialog.form.size_estimate.text().endswith(dialog.review_size_estimate.text())
    dialog.form.mode.setCurrentIndex(0)
    assert dialog.form.size_estimate.text() == estimate
    dialog.form.aspect.setCurrentIndex(1)
    wait_until(lambda dialog=dialog: dialog.previews.result is None)
    result = preview_ready(dialog)
    assert all(profile.image.size == (540, 960) for profile in result.profiles)

    def preset_name(*args: object, **kwargs: object) -> tuple[str, bool]:
        return "Portrait", True

    monkeypatch.setattr(QInputDialog, "getText", preset_name)
    dialog.presets.save_preset.click()
    assert dialog.presets.store.presets()[0].settings.aspect is VideoAspect.PORTRAIT
    dialog.form.aspect.setCurrentIndex(0)
    dialog.presets.load_preset.click()
    assert dialog.form.aspect.currentIndex() == 1
    preview_ready(dialog)
    dialog.next.click()
    assert dialog.review_fields["resolution"].text() == "2160×3840"
    dialog.back.click()
    dialog.form.layout_profile.setCurrentIndex(2)
    result = preview_ready(dialog)
    assert all(profile.image.size == (540, 960) for profile in result.profiles)
    assert dialog.review_fields["resolution"].text() == "1080×1920"
    dialog.form.aspect.setCurrentIndex(0)
    preview_ready(dialog)
    assert dialog.review_fields["resolution"].text() == "1920×1080"
    dialog.form.interval.setCurrentIndex(2)
    preview_ready(dialog)
    dialog.next.click()
    assert not dialog.preview_note.isVisible()
    assert dialog.status.parentWidget() is dialog.progress.parentWidget()
    dialog.close()


def test_export_file_dialogs_preserve_paths_and_successful_output_folder(
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
    browse = next(
        button for button in dialog.findChildren(QPushButton) if button.text() == "Browse…"
    )
    for configured in ("absolute", "relative", "directory", "missing", "empty"):
        with TemporaryDirectory(dir=".tmp") as temporary:
            folder = Path(temporary).resolve() / f"{configured} encoder folder"
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
            dialog.form.encoder.setText(original)
            starts: list[str] = []
            answer = [""]

            def choose(*args: object, **kwargs: object) -> tuple[str, str]:
                starts.append(str(args[2]))
                return answer[0], ""

            monkeypatch.setattr(QFileDialog, "getOpenFileName", choose)
            browse.click()
            assert starts[-1] == ("" if configured == "empty" else str(folder))
            assert dialog.form.encoder.text() == original
            other = folder / "other"
            other.mkdir()
            answer[0] = str(other / "ffmpeg.exe")
            browse.click()
            assert dialog.form.encoder.text() == answer[0]
            answer[0] = ""
            browse.click()
            assert starts[-1] == str(other)
            assert dialog.form.encoder.text() == str(other / "ffmpeg.exe")

    dialog.close()

    from ride_forces_analyzer.ui.exports import video as ui_export
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
            return (str(output), "") if len(suggestions) <= 2 else ("", "")

        monkeypatch.setattr(QFileDialog, "getSaveFileName", destination)

        def encoder(path: Path | None = None) -> Path:
            return Path(__file__)

        def export(*args: object, **kwargs: object) -> Path:
            assert kwargs["overwrite"] is output.exists()
            output.write_bytes(b"complete video")
            return output

        monkeypatch.setattr(ui_export, "find_ffmpeg", encoder)
        monkeypatch.setattr(ui_workers, "export_video", export)
        dialog.start.click()
        wait_until(lambda: dialog.worker is None)
        assert Path(suggestions[0]).name == source.stem + " - Flow Ribbon.mov"
        assert Preferences(dialog.preferences.path).export_directory() == str(output.parent)
        dialog.start.click()
        wait_until(lambda: dialog.worker is None)
        assert output.read_bytes() == b"complete video"
        dialog.back.click()
        dialog.form.layout_profile.setCurrentIndex(2)
        dialog.form.mode.setCurrentIndex(1)
        preview_ready(dialog)
        dialog.next.click()
        dialog.start.click()
        assert Path(suggestions[2]) == output.parent / (source.stem + " - HUD.mp4")
        assert dialog.preferences.export_directory() == str(output.parent)
    dialog.close()


def test_export_worker_progress_cancel_and_gui_recovery(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui.exports import video as ui_export
    from ride_forces_analyzer.rendering.encoding import ExportCancelled

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    dialog.form.layout_profile.setCurrentIndex(3)
    wait_until(lambda: dialog.previews.result is not None)
    dialog.next.click()
    started = Event()

    def fake_export(*args: object, **kwargs: object) -> Path:
        from ride_forces_analyzer.rendering.model import ExportTimeline

        assert isinstance(args[0], ExportTimeline)
        assert args[0].settings.layout == ExportLayout.ORBIT
        assert kwargs["render_jobs"] == window.preferences.render_jobs()
        started.set()
        cancelled = kwargs["cancelled"]
        assert isinstance(cancelled, Event)
        if not cancelled.wait(5):
            raise RuntimeError("Test cancellation was not delivered")
        raise ExportCancelled()

    monkeypatch.setattr(ui_workers, "export_video", fake_export)

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
    dialog.worker.signals.progress.emit(ExportProgress(ExportPhase.RENDERING, 100, 1000, 10))
    wait_until(lambda: dialog.progress.value() == 10)
    wait_until(lambda: "1:30" in dialog.eta.text())
    dialog.worker.signals.progress.emit(ExportProgress(ExportPhase.FINALIZING, 1000, 1000, 100))
    wait_until(lambda: dialog.eta.text() == "Frames complete · finalizing video…")
    dialog.reject()
    assert dialog.isVisible()
    assert not window.close()  # A close requests cancellation, never abandons a live worker.
    wait_until(lambda: dialog.worker is None)
    QThreadPool.globalInstance().waitForDone()
    assert dialog.start.isEnabled()
    assert "cancelled" in dialog.status.text()
    assert dialog.eta.text() == ""
    dialog.close()


def test_stale_preview_is_discarded_after_fast_profile_changes(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.analysis.recording import RecordingAnalysis
    from ride_forces_analyzer.rendering.model import ExportLayout, ExportSettings
    from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition

    original = ui_workers.build_previews
    started, release = Event(), Event()
    calls: list[tuple[str, int | str]] = []

    def delayed(
        data: RecordingAnalysis,
        settings: ExportSettings,
        first: int,
        last: int,
        sample: int,
        background: PreviewBackground,
        previous_positions: dict[ExportLayout, LayoutPosition],
    ) -> ExportPreview:
        assert isinstance(background, PreviewBackground)
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
            background,
            previous_positions,
        )

    monkeypatch.setattr(ui_workers, "build_previews", delayed)
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog)
    try:
        wait_until(started.is_set)
        dialog.form.layout_profile.setCurrentIndex(3)
        dialog.form.fps.setCurrentText("30")
        assert dialog.previews.result is None and not dialog.next.isEnabled()
    finally:
        release.set()
    wait_until(lambda: dialog.previews.result is not None)
    assert calls == [
        (ExportLayout.RIBBON, StandardFrameRate.FPS_50),
        (ExportLayout.ORBIT, StandardFrameRate.FPS_30),
    ]
    assert dialog.form.layout_profile.currentText() == "G-Orbit"
    assert "Preview: graph sample" in dialog.preview_caption.text()
    assert dialog.next.isEnabled() and dialog.worker is None
    dialog.reject()
    assert dialog.previews.closing and not dialog.isVisible()


def test_saved_presets_and_recording_queue_survive_assistant_reopen(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui.exports.batches import BatchDialog
    from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition

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
    dialog.form.layout_profile.setCurrentIndex(3)
    dialog.form.position.setCurrentIndex(
        dialog.form.position.findData(LayoutPosition.TOP_RIGHT.value),
    )
    dialog.form.fps.setCurrentText("59.94")
    dialog.form.smoothing.setCurrentIndex(1)
    dialog.form.seconds.setValue(12.5)
    dialog.form.interval.setCurrentIndex(2)
    dialog.presets.save_preset.click()
    dialog.presets.queue.click()
    dialog.form.layout_profile.setCurrentIndex(0)
    dialog.form.fps.setCurrentText("50")
    dialog.form.smoothing.setCurrentIndex(5)
    dialog.presets.save_preset.click()
    dialog.presets.queue.click()
    saved = dialog.presets.store.batch("Weekend")
    assert len(saved.jobs) == 2
    assert saved.jobs[0].preset.settings.layout == ExportLayout.ORBIT
    assert saved.jobs[0].preset.settings.fps == "60000/1001"
    assert saved.jobs[0].preset.settings.position is LayoutPosition.TOP_RIGHT
    assert saved.jobs[0].preset.smoothing_window == 3
    assert saved.jobs[0].preset.analysis_configuration is not None
    assert saved.jobs[1].preset.settings.layout == ExportLayout.RIBBON
    dialog.form.fps.setCurrentText("25")
    dialog.presets.update_preset.click()
    assert (
        dialog.presets.store.batch("Weekend").jobs[1].preset.settings.fps
        is StandardFrameRate.FPS_50
    )
    dialog.close()
    window.export_button.click()
    reopened = window.export_window
    assert isinstance(reopened, ExportDialog)
    assert reopened.presets.preset_selector.count() == 3
    reopened.presets.preset_selector.setCurrentText("Orbit5994")
    reopened.presets.load_preset.click()
    preview_ready(reopened)
    assert reopened.form.layout_profile.currentIndex() == 3
    assert reopened.form.position.currentData() == LayoutPosition.TOP_RIGHT
    assert reopened.form.fps.currentText() == "59.94" and reopened.form.seconds.value() == 12.5
    assert (
        reopened.form.smoothing.currentIndex() == 1 and reopened.form.interval.currentIndex() == 2
    )
    assert "3 samples" in reopened.form.smoothing.toolTip()
    assert window.data is not None and window.data.calibration_available
    assert window.data.smoothing_window == 11
    reopened.presets.manage_batches.click()
    assert isinstance(reopened.presets.batch_window, BatchDialog)
    assert reopened.presets.batch_window.table.rowCount() == 2
    reopened.close()


def test_batch_editor_multi_ride_presets_and_run_all_cancellation(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui.exports import batches as ui_batches
    from ride_forces_analyzer.storage.exports import ExportStore, default_database_path
    from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset
    from ride_forces_analyzer.rendering.model import ExportSettings
    from ride_forces_analyzer.exports.batches import BatchReport, JobResult

    store = ExportStore(default_database_path())
    store.save_preset(
        SavedPreset(
            name="Ribbon",
            settings=ExportSettings(layout=ExportLayout.RIBBON),
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            smoothing_window=11,
            range_mode="markers",
        ),
    )
    store.save_preset(
        SavedPreset(
            name="Orbit",
            settings=ExportSettings(layout=ExportLayout.ORBIT),
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            smoothing_window=11,
            range_mode="markers",
        ),
    )
    store.create_batch("Day1")
    window = explorer_window
    window.preferences.remember_render_jobs(4)
    assert window.data is None and window.batches_button.isEnabled()
    window.batches_button.click()
    dialog = window.batch_window
    assert isinstance(dialog, ui_batches.BatchDialog)
    dialog.presets.selectAll()

    def files(*args: object, **kwargs: object) -> tuple[list[str], str]:
        assert args[3] == "Ride Forces (*.forces *.zforces)"
        return [
            str(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.zforces"))),
            str(next(REAL_FIXTURE_DIRECTORY.glob("Kraken-*.forces"))),
        ], ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", files)
    dialog.add.click()
    wait_until(lambda: dialog.builder is None)
    assert dialog.table.rowCount() == 4
    assert len(store.batch("Day1").jobs) == 4
    store.save_batch(SavedBatch(name="Day2", jobs=store.batch("Day1").jobs[:1], schema_version=1))
    dialog.refresh("Day1")
    started = Event()
    names: list[str] = []

    def fake_run(batches: tuple[SavedBatch, ...], directory: Path, **kwargs: object) -> BatchReport:
        assert kwargs["render_jobs"] == window.preferences.render_jobs()
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
    dialog.worker.signals.progress.emit(
        1,
        5,
        ExportProgress(ExportPhase.RENDERING, 1, 2, 10),
        "Day1 · Manta · Orbit",
    )
    wait_until(lambda: dialog.progress.value() == 10)
    assert "Manta" in dialog.current_job.text()
    assert dialog.export_progress.value() == 50
    assert "0:10" in dialog.eta.text()
    dialog.worker.signals.progress.emit(
        1,
        5,
        ExportProgress(ExportPhase.FINALIZING, 2, 2, 20),
        "Day1 · Manta · Orbit",
    )
    wait_until(lambda: "finalizing" in dialog.eta.text())
    dialog.worker.signals.progress.emit(1, 5, None, "Day1 · Manta · Orbit")
    wait_until(lambda: dialog.progress.value() == 20)
    assert dialog.eta.text() == ""
    dialog.worker.signals.progress.emit(
        2,
        5,
        ExportProgress(ExportPhase.PREPARING),
        "Day1 · Kraken · Orbit",
    )
    wait_until(lambda: dialog.export_progress.value() == 0)
    assert dialog.progress.value() == 20
    assert "estimating" in dialog.eta.text()
    assert not window.close()
    wait_until(lambda: dialog.worker is None)
    assert dialog.last_report is not None and len(dialog.last_report.results) == 5
    assert "5 cancelled" in dialog.status.text()
    assert dialog.eta.text() == ""
    assert len(store.batch("Day1").jobs) == 4
    dialog.table.selectAll()
    dialog.remove.click()
    assert store.batch("Day1").jobs == ()
    dialog.delete.click()
    assert [batch.name for batch in store.batches()] == ["Day2"]
    dialog.close()


def test_loading_analysis_recipe_keeps_workspace_snapshot_and_independent_stages(
    explorer_window: ExplorerWindow,
) -> None:
    from dataclasses import replace
    from ride_forces_analyzer.analysis.recording import AnalysisStage
    from ride_forces_analyzer.storage.export_models import make_preset
    from ride_forces_analyzer.storage.exports import ExportStore
    from ride_forces_analyzer.ui.exports.video import default_database_path
    from ride_forces_analyzer.rendering.model import ExportSettings

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None and window.data.analysis is not None
    snapshot = window.data.analysis
    configuration = replace(snapshot.configuration, context_input=AnalysisStage.PROJECTION)
    store = ExportStore(default_database_path())
    store.save_preset(make_preset("Source context", ExportSettings(), 11, "markers", configuration))
    window.export_button.click()
    dialog = window.export_window
    assert isinstance(dialog, ExportDialog) and dialog.data.analysis is snapshot
    dialog.presets.preset_selector.setCurrentText("Source context")
    dialog.presets.load_preset.click()
    changed = dialog.data.analysis
    assert changed is not None and changed.configuration == configuration
    assert changed.forces is snapshot.forces and changed.orientation is snapshot.orientation
    assert changed.context is not snapshot.context
    assert window.data.analysis is snapshot
    preview_ready(dialog)
    dialog.close()
