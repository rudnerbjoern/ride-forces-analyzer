"""Qt background transport for immutable preview and video-export jobs.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error

# cspell:words pixmap Deutsch

from pathlib import Path
from threading import Event

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.exports.history import ExportAttempt
from ride_forces_analyzer.storage.library_history import ExportRequest
from ride_forces_analyzer.rendering.encoding import ExportCancelled, export_video
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSettings,
    ExportTimeline,
)
from ride_forces_analyzer.rendering.preview import (
    PreviewBackground,
    build_previews,
    preview_rendered_region,
)
from ride_forces_analyzer.rendering.progress import ExportProgress
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition


class PreviewSignals(QObject):
    """Deliver preview completion and failure notifications to the owning dialog.

    Attributes:
        ready: Qt signal for ready notifications.
        failed: Qt signal for failed notifications.
    """

    ready = Signal(int, object)
    failed = Signal(int, str)


class PreviewWorker(QRunnable):
    """Build layout previews in the thread pool from one captured analysis snapshot.

    Attributes:
        revision: Monotonically increasing identity used to reject superseded work.
        analysis: Prepared recording-analysis snapshot used by this operation.
        settings: Validated settings controlling this operation.
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
        sample: Source sample index to inspect or present.
        background: Preview background, excluded from exported overlays.
        previous_positions: Previously selected positions keyed by layout.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(
        self,
        revision: int,
        analysis: RecordingAnalysis,
        settings: ExportSettings,
        first: int,
        last: int,
        sample: int,
        background: PreviewBackground,
        previous_positions: dict[ExportLayout, LayoutPosition],
    ) -> None:
        """Initialize preview worker and its owned state.

        Args:
            revision: Monotonically increasing identity used to reject superseded work.
            analysis: Prepared recording-analysis snapshot used by this operation.
            settings: Validated settings controlling this operation.
            first: First included source sample index.
            last: Last included source sample index.
            sample: Source sample index to inspect or present.
            background: Preview background, excluded from exported overlays.
            previous_positions: Previously selected positions keyed by layout.

        Returns:
            None.
        """
        super().__init__()
        self.revision, self.analysis, self.settings = revision, analysis, settings
        self.first, self.last, self.sample, self.background = first, last, sample, background
        self.previous_positions = previous_positions.copy()
        self.signals = PreviewSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            result = build_previews(
                self.analysis,
                self.settings,
                self.first,
                self.last,
                self.sample,
                self.background,
                self.previous_positions,
            )
        except Exception as error:
            record_error("Export preview", error)
            self.signals.failed.emit(self.revision, str(error))
        else:
            self.signals.ready.emit(self.revision, result)


class ExportSignals(QObject):
    """Deliver video-export progress, completion and failure notifications.

    Attributes:
        saved: Qt signal for saved notifications.
        progress: Qt signal for progress notifications.
        preview: Qt signal carrying an export frame index and its display image.
        finished: Qt signal for finished notifications.
        failed: Qt signal for failed notifications.
    """

    saved = Signal(str)
    progress = Signal(object)
    preview = Signal(int, object)
    finished = Signal(str)
    failed = Signal(str)


class ExportWorker(QRunnable):
    """Run the bound video export and transport its result through Qt signals.

    Attributes:
        timeline: Bound video timeline containing the source interval and export settings.
        destination: Requested output path; replacement follows the explicit overwrite
            policy.
        ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
        render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
            availability.
        background: Display-only backdrop used for live frame previews.
        overwrite: Whether the caller explicitly permits replacing an existing
            destination.
        cancelled: Event used to request cancellation without publishing partial output.
        signals: Qt result, failure and progress signal transport owned by the worker.
        attempt: History lifecycle started before preparation, or created on execution.
    """

    def __init__(
        self,
        timeline: ExportTimeline,
        destination: Path,
        ffmpeg: Path,
        *,
        render_jobs: int = 1,
        overwrite: bool = False,
        background: PreviewBackground = PreviewBackground.CHECKER,
        attempt: ExportAttempt | None = None,
    ) -> None:
        """Initialize export worker and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.
            destination: Requested output path; replacement follows the explicit overwrite
                policy.
            ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
            render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
                availability.
            overwrite: Whether the caller explicitly permits replacing an existing
                destination.
            background: Display-only backdrop used for live frame previews.
            attempt: Optional history lifecycle covering earlier preparation.

        Returns:
            None.
        """
        super().__init__()
        self.timeline = timeline
        self.destination = destination
        self.ffmpeg = ffmpeg
        self.render_jobs = render_jobs
        self.overwrite = overwrite
        self.background = background
        self.attempt = attempt
        self.cancelled = Event()
        self.signals = ExportSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        attempt = self.attempt or ExportAttempt(
            ExportRequest.capture(
                self.timeline.analysis,
                "video",
                self.timeline.first,
                self.timeline.last,
                self.timeline.settings,
            ),
        )
        attempt.resume()
        attempt.prepared(self.timeline.snapshot)
        gpu: bool | None = None
        try:

            def progress(update: ExportProgress) -> None:
                nonlocal gpu
                if update.use_gpu is not None:
                    gpu = update.use_gpu
                self.signals.progress.emit(update)

            def preview(frame: int, raw: bytes) -> None:
                image = preview_rendered_region(self.timeline, raw, self.background)
                self.signals.preview.emit(frame, image)

            path = export_video(
                self.timeline,
                self.destination,
                ffmpeg=self.ffmpeg,
                cancelled=self.cancelled,
                progress=progress,
                frame_preview=preview,
                render_jobs=self.render_jobs,
                overwrite=self.overwrite,
            )
        except ExportCancelled:
            attempt.finish("cancelled", gpu=gpu, error="Export cancelled")
            message = tr("Export cancelled. No incomplete output was kept.")
            self.signals.finished.emit(self._history_message(message, attempt))
        except Exception as error:
            record_error("Video export", error)
            attempt.finish("failed", gpu=gpu, error=str(error))
            self.signals.failed.emit(
                self._history_message(tr("Export failed: {0}", error), attempt),
            )
        else:
            attempt.finish("completed", output=path, gpu=gpu)
            self.signals.saved.emit(str(path))
            self.signals.finished.emit(self._history_message(tr("Saved {0}", path), attempt))

    def _history_message(self, message: str, attempt: ExportAttempt) -> str:
        return (
            f"{message}\n{tr('Export history could not be saved: {0}', attempt.warning)}"
            if attempt.warning
            else message
        )
