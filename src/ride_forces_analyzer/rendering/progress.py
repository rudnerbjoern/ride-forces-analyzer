"""Shared export status and frame-time estimates, independent of widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from enum import StrEnum
from math import ceil


def remaining_seconds(elapsed: float, completed: int, total: int) -> int | None:
    """Estimate pending frames using the average elapsed time per completed frame.

    Args:
        elapsed: Elapsed processing time in seconds.
        completed: Number of completed frames.
        total: Total number of frames or items to process.

    Returns:
        Estimated remaining seconds, or None before a useful estimate is available.
    """
    if completed <= 0 or elapsed <= 0 or total <= 0:
        return None
    return ceil(elapsed / completed * max(0, total - completed))


class ExportPhase(StrEnum):
    """Stages of a single video export, independent of UI transport.

    Attributes:
        PREPARING: Discover the encoder and probe the requested backend.
        RENDERING: Generate frames and submit them to the encoder.
        FINALIZING: Finish encoding and publish the completed output file.
        COMPLETED: The output file has been successfully published.
    """

    PREPARING = "preparing"
    RENDERING = "rendering"
    FINALIZING = "finalizing"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ExportProgress:
    """Immutable video status shared by single and batch exports.

    Attributes:
        phase: Current export stage; completion requires successful publication.
        completed_frames: Rendered frames submitted to the encoder, not encoded frames.
        total_frames: Expected number of output frames; zero before batch preparation.
        elapsed_seconds: Monotonic time since this video's export started.
        use_gpu: Actual probed backend, or None before backend selection.
    """

    phase: ExportPhase
    completed_frames: int = 0
    total_frames: int = 0
    elapsed_seconds: float = 0.0
    use_gpu: bool | None = None

    @property
    def percent(self) -> int:
        """Return submitted-frame progress.

        Returns:
            Integer percentage, or zero before the frame count is known. A value
            of 100 means all frames were submitted, not that publication is complete.
        """
        return self.completed_frames * 100 // max(1, self.total_frames)

    @property
    def remaining_seconds(self) -> int | None:
        """Estimate time for pending frames from this export's measured throughput.

        Returns:
            Remaining seconds, or None before useful throughput or outside rendering.
        """
        if self.phase is not ExportPhase.RENDERING:
            return None
        return remaining_seconds(self.elapsed_seconds, self.completed_frames, self.total_frames)
