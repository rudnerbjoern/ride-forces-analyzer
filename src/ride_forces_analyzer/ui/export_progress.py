"""Shared presentation of renderer-owned export status.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtWidgets import QLabel, QProgressBar

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress
from .translation import bind


def show_export_progress(
    update: ExportProgress,
    bar: QProgressBar,
    status: QLabel,
    eta: QLabel,
) -> None:
    """Present shared status without calculating throughput or owning an export clock.

    Args:
        update: Immutable renderer status with its remaining-frame estimate.
        bar: Progress bar showing submitted frames for this video.
        status: Label receiving the localized processing phase/backend.
        eta: Label receiving the localized estimate or finalization notice.

    Returns:
        None.
    """
    bar.setValue(update.percent)
    bar.setFormat(
        f"{update.completed_frames:,} / {update.total_frames:,} · %p%"
        if update.total_frames
        else "%p%",
    )
    if update.phase is ExportPhase.PREPARING:
        bind(status, tr("Preparing export…"), "text")
        bind(eta, tr("Remaining frame time: estimating…"), "text")
    elif update.phase is ExportPhase.FINALIZING:
        bind(status, tr("Finalizing video…"), "text")
        bind(eta, tr("Frames complete · finalizing video…"), "text")
    elif update.phase is ExportPhase.COMPLETED:
        bind(eta, "", "text")
    else:
        bind(
            status,
            tr(
                "Encoding on NVIDIA GPU"
                if update.use_gpu
                else "Encoding on CPU (GPU unavailable or disabled)",
            ),
            "text",
        )
        seconds = update.remaining_seconds
        bind(
            eta,
            tr("Remaining frame time: estimating…")
            if seconds is None
            else tr(
                "Remaining frame time: about {0}:{1:02d} (min:sec)",
                seconds // 60,
                seconds % 60,
            ),
            "text",
        )
