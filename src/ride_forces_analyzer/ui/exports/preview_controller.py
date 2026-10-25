"""Debounced preview scheduling and stale-result handling for export dialogs.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal, Slot

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.rendering.model import ExportLayout, ExportSettings
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.rendering.preview import ExportPreview, PreviewBackground
from .workers import PreviewWorker


class PreviewController(QObject):
    """Run one preview worker at a time and adopt only its current revision.

    Attributes:
        ready: Signal delivering an accepted production preview.
        failed: Signal delivering a current preview failure description.
        worker: Active preview worker, or None while idle.
        result: Most recently accepted preview, invalidated on input changes.
        revision: Monotonically increasing preview intent revision.
        timer: Single-shot debounce timer for pending input changes.
        closing: Whether shutdown has started and results must be ignored.
        _request: Latest captured snapshot, settings, interval and preview context.
    """

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject) -> None:
        """Create stopped preview transport owned by the dialog.

        Args:
            parent: Object owning the timer and controller lifetime.

        Returns:
            None.
        """
        super().__init__(parent)
        self.worker: PreviewWorker | None = None
        self.result: ExportPreview | None = None
        self.revision = 0
        self.closing = False
        self._request: (
            tuple[
                RecordingAnalysis,
                ExportSettings,
                int,
                int,
                int,
                PreviewBackground,
                dict[ExportLayout, LayoutPosition],
            ]
            | None
        ) = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self._request_preview)

    def schedule(
        self,
        analysis: RecordingAnalysis,
        settings: ExportSettings,
        first: int,
        last: int,
        sample: int,
        background: PreviewBackground,
        positions: dict[ExportLayout, LayoutPosition],
    ) -> None:
        """Capture the latest preview inputs and restart the debounce timer.

        Args:
            analysis: Immutable prepared snapshot consumed by the worker.
            settings: Current validated export settings.
            first: First included export sample.
            last: Last included export sample.
            sample: Exact selected source sample to preview.
            background: Display-only preview background.
            positions: Retained layout placement choices to copy for this request.

        Returns:
            None.
        """
        self.revision += 1
        self.result = None
        self._request = (analysis, settings, first, last, sample, background, positions.copy())
        self.timer.start()

    @Slot()
    def _request_preview(self) -> None:
        if (
            self.closing
            or self.worker is not None
            or self.result is not None
            or self._request is None
        ):
            return
        self.timer.stop()
        worker = PreviewWorker(self.revision, *self._request)
        worker.signals.ready.connect(self._preview_ready)
        worker.signals.failed.connect(self._preview_failed)
        self.worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(int, object)
    def _preview_ready(self, revision: int, result: object) -> None:
        self.worker = None
        if self.closing:
            return
        if revision != self.revision:
            self._request_preview()
            return
        if not isinstance(result, ExportPreview):
            return
        self.result = result
        self.ready.emit(result)

    @Slot(int, str)
    def _preview_failed(self, revision: int, message: str) -> None:
        self.worker = None
        if self.closing:
            return
        if revision != self.revision:
            self._request_preview()
            return
        self.failed.emit(message)

    def close(self) -> None:
        """Stop scheduling and ignore worker completion after dialog shutdown.

        Returns:
            None; an already running preview worker finishes through its normal path.
        """
        self.closing = True
        self.timer.stop()
