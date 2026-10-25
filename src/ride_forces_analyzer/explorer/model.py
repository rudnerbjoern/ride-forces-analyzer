"""Qt-independent explorer state bound to original data and prepared analysis.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from math import ceil, floor, isfinite
from ride_forces_analyzer.analysis.extrema import SelectionExtrema, calculate_extrema
from ride_forces_analyzer.importers import ImportSuccess

from . import selection, text
from .selection import SampleRange

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray
    from ride_forces_analyzer.analysis.recording import RecordingAnalysis

    type PlotChannel = tuple[float, ...] | NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class ExplorerData:
    """Explorer data contract and owned data.

    Attributes:
        source: Retained input identity or image; its original representation remains
            owned.
        channels: Prepared channels to inspect or display.
        title: Recording or layout title shown without interpreting its contents.
        summary: Prepared recording summary.
        notes: Retained diagnostic text for the recording or current operation.
        value_range: Visible force-value range.
        calibrated_enabled: Whether calibrated channels are selected.
        calibration_error: Reason calibration is unavailable, when present.
        analysis: Prepared recording-analysis snapshot used by this operation.
        _prepared_channels: Cached channels prepared for the explorer.
    """

    source: ImportSuccess
    channels: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
    title: str
    summary: str
    notes: str
    value_range: tuple[float, float]
    calibrated_enabled: bool = False
    calibration_error: str | None = None
    analysis: "RecordingAnalysis | None" = None
    _prepared_channels: "tuple[PlotChannel, PlotChannel, PlotChannel] | None" = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Analysis belongs to another import.
        """
        if self.analysis is not None and self.analysis.source is not self.source:
            raise ValueError("Analysis belongs to another import")
        channels = self.analysis.forces.smoothed.channels if self.analysis is not None else None
        prepared = (
            (channels[0].values, channels[1].values, channels[2].values) if channels else None
        )
        object.__setattr__(self, "_prepared_channels", prepared)

    @property
    def calibration_available(self) -> bool:
        """Whether the bound snapshot has a prepared calibrated force stage.

        Returns:
            True when the requested check succeeds or the event is handled; otherwise False.
        """
        return self._prepared_channels is not None

    @property
    def smoothing_window(self) -> int:
        """Read the snapshot recipe; 11 is the default before analysis is available.

        Returns:
            Configured odd smoothing-window size in samples.

        Raises:
            AssertionError: If a required internal invariant does not hold.
        """
        if self.analysis is None:
            return 11
        window = dict(self.analysis.configuration.smoothing.parameters).get("window_samples", 11)
        assert type(window) is int
        return window

    def vertical_context_label(self, index: int) -> str | None:
        """Format the prepared sample category without classifying forces again.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Localized context label, or None when classification is unavailable.
        """
        return text.vertical_context_label(self, index)

    @property
    def localized_notes(self) -> str:
        """Return localized diagnostic text while retaining original diagnostics.

        Returns:
            Localized diagnostic text while retaining original diagnostics.
        """
        return text.localized_notes(self)

    @property
    def plotted_channels(self) -> "tuple[PlotChannel, PlotChannel, PlotChannel]":
        """Return the three channels selected for raw or calibrated display.

        Returns:
            The three channels selected for raw or calibrated display.
        """
        if self.calibrated_enabled and self._prepared_channels is not None:
            return self._prepared_channels
        return self.channels

    @property
    def channel_names(self) -> tuple[str, str, str]:
        """Return the display names of the currently plotted channels.

        Returns:
            The display names of the currently plotted channels.
        """
        return text.channel_names(self)

    @property
    def vertical_context_segments(self) -> tuple[tuple[str, int, int], ...]:
        """Inclusive drawing ranges sharing boundary points, only for calibrated g.

        Returns:
            Context labels and inclusive source-index intervals for drawing.
        """
        if not self.calibrated_enabled or self.analysis is None:
            return ()
        categories = self.analysis.context.labels
        if categories is None:
            return ()
        labels = tuple(label.value.replace("_", " ").title() for label in categories)
        if not labels:
            return ()
        segments: list[tuple[str, int, int]] = []
        start = 0
        for index in range(1, len(labels)):
            if labels[index] != labels[start]:
                segments.append((labels[start], start, index))
                start = index
        segments.append((labels[start], start, len(labels) - 1))
        return tuple(segments)

    def with_calibration(self, enabled: bool) -> "ExplorerData":
        """Create presentation data using the requested available force view.

        Args:
            enabled: Whether the requested presentation or stored preference is enabled.

        Returns:
            New explorer data using the selected calibrated or source force view.
        """
        active = enabled and self.calibration_available
        channels = self._prepared_channels if active and self._prepared_channels else self.channels
        finite = [float(value) for axis in channels for value in axis if isfinite(value)]
        low = min(0.0, min(finite, default=0.0))
        high = max(0.0, max(finite, default=0.0))
        bounds = (float(low * 1.05), float(high * 1.05)) if low < high else (-1.0, 1.0)
        if active:
            bounds = (min(-1.05, bounds[0]), max(1.05, bounds[1]))
        return replace(self, calibrated_enabled=active, value_range=bounds)

    @property
    def value_ticks(self) -> tuple[float, ...]:
        """Return suitable value-axis ticks for the prepared display range.

        Returns:
            Suitable value-axis ticks for the prepared display range.
        """
        low, high = self.value_range
        if self.calibrated_enabled and floor(high) - ceil(low) <= 20:
            ticks = {float(value) for value in range(ceil(low), floor(high) + 1)}
        else:
            ticks = {low * (1 - step / 4) + high * (step / 4) for step in range(5)}
        if self.calibrated_enabled:
            ticks.update((-1.0, 0.0, 1.0))
        return tuple(sorted(ticks))

    @property
    def smoothing_text(self) -> str:
        """Return the localized description of the current smoothing window.

        Returns:
            The localized description of the current smoothing window.
        """
        return text.smoothing_text(self)

    def with_smoothing(self, window: int) -> "ExplorerData":
        """Create presentation data bound to the requested smoothing configuration.

        Args:
            window: Odd number of source samples in the smoothing window.

        Returns:
            New explorer data bound to the requested smoothing recipe.
        """
        if self.analysis is None:
            return self
        return self.with_analysis(
            self.analysis.with_smoothing(
                window,
                revision=self.analysis.revision + 1,
                calculation_time=datetime.now(UTC),
            ),
        )

    def with_analysis(self, analysis: "RecordingAnalysis") -> "ExplorerData":
        """Adapt a matching completed snapshot without repeating numerical analysis.

        Args:
            analysis: Prepared recording-analysis snapshot used by this operation.

        Returns:
            New explorer data bound to the matching completed analysis snapshot.

        Raises:
            ValueError: Analysis belongs to another import.
        """
        if analysis.source is not self.source:
            raise ValueError("Analysis belongs to another import")
        reason = analysis.forces.smoothed.availability.reason
        error = reason.message if reason is not None else None
        return replace(
            self,
            analysis=analysis,
            calibration_error=error,
            notes=text.import_notes(self.source, error),
        ).with_calibration(self.calibrated_enabled)

    @property
    def metadata_fields(self) -> tuple[tuple[str, str], ...]:
        """Return the recording metadata as localized label/value pairs.

        Returns:
            The recording metadata as localized label/value pairs.
        """
        return text.metadata_fields(self)

    @property
    def metadata_text(self) -> str:
        """Return formatted recording metadata for the inspector.

        Returns:
            Formatted recording metadata for the inspector.
        """
        return text.metadata_text(self)

    @property
    def metadata_rows_text(self) -> str:
        """Return the recording's row, seat and train metadata when available.

        Returns:
            The recording's row, seat and train metadata when available.
        """
        return text.metadata_rows_text(self)

    @property
    def overview_text(self) -> str:
        """Return the compact recording overview used by the workspace header.

        Returns:
            The compact recording overview used by the workspace header.
        """
        return text.overview_text(self)

    @property
    def availability_text(self) -> str:
        """Describe available calibration, gravity, GPS and time information.

        Returns:
            Localized description of available recording capabilities.
        """
        return text.availability_text(self)

    def sample_clock_text(self, index: int) -> str:
        """Format recording and replay clocks for one source sample.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Localized recording and replay clock text.
        """
        return text.sample_clock_text(self, index)

    def sample_cards(self, index: int) -> tuple[tuple[str, str, str], ...]:
        """Format the three force cards for one source sample.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Three force readouts, each containing its name, formatted value and availability
            hint.
        """
        return text.sample_cards(self, index)

    def selection_extrema(self, first: int, last: int) -> SelectionExtrema:
        """Read extrema from the prepared channels over an inclusive selection.

        Args:
            first: First included source sample index.
            last: Last included source sample index.

        Returns:
            Extrema and source-time context for the inclusive selection.
        """
        return calculate_extrema(
            self.source,
            first,
            last,
            forces=self.analysis.forces.smoothed
            if self.calibrated_enabled and self.analysis is not None
            else None,
        )

    def extrema_text(
        self,
        first: int,
        last: int,
        *,
        rich: bool = False,
    ) -> tuple[str, tuple[str, ...]]:
        """Format the selected interval's extrema and calculation context.

        Args:
            first: First included source sample index.
            last: Last included source sample index.
            rich: Whether to emit supported rich-text formatting instead of plain text.

        Returns:
            Selection description and formatted per-channel extrema.
        """
        return text.extrema_text(self, first, last, rich=rich)

    @property
    def count(self) -> int:
        """Return the number of retained samples or items represented by this object.

        Returns:
            The number of retained samples or items represented by this object.
        """
        return len(self.channels[0])

    @property
    def markers(self) -> tuple[tuple[str, int], ...]:
        """Return named source or effective marker indices for chart presentation.

        Returns:
            Named source or effective marker indices for chart presentation.
        """
        indices = self.source.recording.indices
        first, last = self.ride_bounds
        calibration = self.analysis.configuration.calibration if self.analysis is not None else None
        overrides = {
            "gravityIndex": calibration.gravity_index if calibration is not None else None,
            "inclineIndex": calibration.incline_index if calibration is not None else None,
        }
        return tuple(
            (name, index)
            for name, index in (
                ("startIndex", first),
                ("endIndex", last),
                (
                    "gravityIndex",
                    overrides["gravityIndex"]
                    if overrides["gravityIndex"] is not None
                    else indices.gravity,
                ),
                (
                    "inclineIndex",
                    overrides["inclineIndex"]
                    if overrides["inclineIndex"] is not None
                    else indices.incline,
                ),
            )
            if index is not None
            and (
                self.source.recording.source.root is None
                or name in self.source.recording.source.root
                or overrides.get(name) is not None
                or (
                    self.analysis is not None
                    and self.analysis.configuration.ride_bounds is not None
                    and name in ("startIndex", "endIndex")
                )
            )
        )

    @property
    def ride_bounds(self) -> tuple[int, int]:
        """Return the effective inclusive ride interval.

        Returns:
            The effective inclusive ride interval.
        """
        if self.analysis is not None:
            return self.analysis.ride_bounds
        indices = self.source.recording.indices
        return indices.start, indices.end

    @property
    def default_time_range(self) -> tuple[float, float]:
        """Return the default chart interval in recording seconds.

        Returns:
            The default chart interval in recording seconds.
        """
        return selection.default_time_range(self)

    @property
    def sample_rate(self) -> float:
        """Return the recording's effective source sample rate.

        Returns:
            The recording's effective source sample rate.
        """
        return self.source.recording.motion.sample_rate.value

    @property
    def duration(self) -> float:
        """Elapsed time of the final sample, not an extra acquisition interval.

        Returns:
            Elapsed recording time at the final source sample, in seconds.
        """
        return self.time_at(self.count - 1)

    @property
    def replay_time_label(self) -> str:
        """Return the localized label for the recording's replay time notation.

        Returns:
            The localized label for the recording's replay time notation.
        """
        return text.replay_time_label(self)

    def replay_text(self, index: int) -> str:
        """Format a source sample as start-relative replay time.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Formatted replay time relative to the selected origin.
        """
        return text.replay_text(self, index)

    def time_at(self, index: int) -> float:
        """Convert a source sample index to recording seconds.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Time from the recording origin in seconds.
        """
        return selection.time_at(self, index)

    def sample_at_time(self, seconds: float) -> int:
        """Return the nearest sample, clamped to the recording bounds.

        Args:
            seconds: Time in seconds in the clock or coordinate system used by this operation.

        Returns:
            The nearest sample, clamped to the recording bounds.

        Raises:
            ValueError: Sample time must be finite.
        """
        return selection.sample_at_time(self, seconds)

    def select(self, first: int, last: int) -> SampleRange:
        """Create an inclusive selection from source sample indices.

        Args:
            first: First included source sample index.
            last: Last included source sample index.

        Returns:
            Inclusive selection admitted by this object's bounds or placement contract.

        Raises:
            ValueError: Selection requires bounded, ordered sample indices.
        """
        return selection.select(self, first, last)

    def select_visible(self, low: float, high: float) -> SampleRange:
        """Select the source samples intersecting a visible time interval.

        Args:
            low: Lower bound in the coordinate system declared by the operation.
            high: Upper bound in the coordinate system declared by the operation.

        Returns:
            Inclusive source-sample interval intersecting the visible time range.

        Raises:
            ValueError: Visible range must be finite and ordered.
        """
        return selection.select_visible(self, low, high)

    @property
    def technical_summary(self) -> str:
        """Return retained source and processing details for the technical inspector.

        Returns:
            Retained source and processing details for the technical inspector.
        """
        return text.technical_summary(self)

    def sample_text(self, index: int, *, rich: bool = False) -> str:
        """Format the available values and context for one source sample.

        Args:
            index: Source or collection index selected for this operation.
            rich: Whether to emit supported rich-text formatting instead of plain text.

        Returns:
            Localized values and availability context for the source sample.
        """
        return text.sample_text(self, index, rich=rich)
