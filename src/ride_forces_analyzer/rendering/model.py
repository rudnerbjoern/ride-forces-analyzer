"""Immutable export preparation, time mapping and display contracts; no widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from math import ceil, floor, isfinite
from typing import Literal, overload

from ride_forces_analyzer.analysis.models import SampleValues
from ride_forces_analyzer.analysis.recording import AnalysisConfiguration, RecordingAnalysis
from ride_forces_analyzer.i18n import LANGUAGES, Language
from .layouts.contracts import LayoutPosition

FrameRate = int | Literal["60000/1001"]
EXPORT_FRAME_RATES: tuple[FrameRate, ...] = (24, 25, 30, 50, "60000/1001", 60)

ExportLayout = Literal["column", "ribbon", "corners", "hud", "orbit"]
PROFILES: tuple[tuple[ExportLayout, str], ...] = (
    ("ribbon", "Flow Ribbon"),
    ("corners", "Corner Instruments"),
    ("hud", "HUD"),
    ("orbit", "G-Orbit"),
    ("column", "Four-panel column"),
)


@dataclass(frozen=True, slots=True)
class ExportSettings:
    """Export settings contract and owned data.

    Attributes:
        fps: Selected output frame rate; 59.94 retains its exact fractional
            representation.
        window_seconds: Width of the visible source-time context in seconds.
        output: Output directory or path for generated artifacts.
        invert_vertical: Whether the vertical plot uses the selected inverted display
            direction.
        invert_lateral: Whether the layout uses its supported lateral direction override.
        prefer_gpu: Whether encoding prefers a probed NVIDIA backend with CPU fallback.
        layout: Stable key selecting the overlay renderer.
        aspect: Selected landscape or portrait output format.
        language: Registered language used to translate presentation text and numbers.
        position: Requested source position or named layout placement, as declared by the
            type.
    """

    fps: FrameRate = 50
    window_seconds: float = 12.0
    output: Literal["transparent", "opaque"] = "transparent"
    invert_vertical: bool = True
    invert_lateral: bool = True
    prefer_gpu: bool = True
    layout: ExportLayout = "column"
    aspect: Literal["landscape", "portrait"] = "landscape"
    language: Language = "en"
    position: LayoutPosition | None = None

    @property
    def dimensions(self) -> tuple[int, int]:
        """Return the layout's output canvas width and height in pixels.

        Returns:
            The layout's output canvas width and height in pixels.
        """
        if self.layout == "hud":
            from .layouts.hud import LANDSCAPE, PORTRAIT

            return (PORTRAIT if self.aspect == "portrait" else LANDSCAPE).size
        return (2160, 3840) if self.aspect == "portrait" else (3840, 2160)

    @property
    def frame_rate(self) -> Fraction:
        """Exact encoder rate; retain the fractional ratio rather than rounding to 59.94.

        Returns:
            Exact output frames per second as a rational number.
        """
        return Fraction(self.fps)

    @property
    def fps_label(self) -> str:
        """Return the user-facing frame-rate choice, including exact 59.94 notation.

        Returns:
            The user-facing frame-rate choice, including exact 59.94 notation.
        """
        return "59.94" if self.fps == "60000/1001" else str(self.fps)

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Unsupported overlay language. Unknown export aspect ratio. Frame rate
                must be an integer from 1 to 120 or 60000/1001. Visible time window must be
                from 1 to 60 seconds. Unknown export output mode. Unknown export layout.
        """
        if self.language not in LANGUAGES:
            raise ValueError("Unsupported overlay language")
        if self.aspect not in ("landscape", "portrait"):
            raise ValueError("Unknown export aspect ratio")
        if not (type(self.fps) is int and 1 <= self.fps <= 120) and self.fps != "60000/1001":
            raise ValueError("Frame rate must be an integer from 1 to 120 or 60000/1001")
        if not isfinite(self.window_seconds) or not 1 <= self.window_seconds <= 60:
            raise ValueError("Visible time window must be from 1 to 60 seconds")
        if self.output not in ("transparent", "opaque"):
            raise ValueError("Unknown export output mode")
        if self.layout not in tuple(key for key, _ in PROFILES):
            raise ValueError("Unknown export layout")
        from .layouts.registry import export_region

        export_region(self)


@dataclass(frozen=True, slots=True)
class ExportValues(Sequence[float | None]):
    """Read-only scalar view of a shared stage buffer; invalid rows remain None.

    Attributes:
        samples: Owned sample buffer and validity information in the declared units.
    """

    samples: SampleValues

    def __len__(self) -> int:
        """Return the number of items represented by this object.

        Returns:
            The number of items represented by this object.
        """
        return len(self.samples.valid_rows)

    @overload
    def __getitem__(self, index: int) -> float | None: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[float | None, ...]: ...

    def __getitem__(self, index: int | slice) -> float | None | tuple[float | None, ...]:
        """Read the requested item or slice without mutating the retained data.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            The float | None | tuple[float | None, ...] result of the operation described
            above.
        """
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(len(self))))
        return float(self.samples.values[index]) if self.samples.valid_rows[index] else None


def prepare_export_analysis(
    analysis: RecordingAnalysis,
    configuration: AnalysisConfiguration,
) -> RecordingAnalysis:
    """Bind matching work or recalculate only changed stages, without changing the source.

    Args:
        analysis: Prepared recording-analysis snapshot used by this operation.
        configuration: Requested immutable analysis or export configuration.

    Returns:
        Analysis matching the captured configuration, reusing compatible prepared stages.
    """
    if configuration == analysis.configuration:
        return analysis
    return analysis.with_configuration(
        configuration,
        revision=analysis.revision + 1,
        calculation_time=datetime.now(UTC),
    )


@dataclass(frozen=True, slots=True)
class ExportChannel:
    """Export channel contract and owned data.

    Attributes:
        name: Stable identifier or displayed name for this model or view.
        unit: Declared unit and its evidence; unknown source units remain unknown.
        color: Color assigned to this channel.
        hint: Explanatory text associated with the channel.
        values: Retained or prepared values in the owning object's declared units.
        low: Lower bound in the coordinate system declared by the operation.
        high: Upper bound in the coordinate system declared by the operation.
        inverted: Whether the displayed channel direction is inverted.
    """

    name: str
    unit: str
    color: str
    hint: str
    values: Sequence[float | None]
    low: float
    high: float
    inverted: bool

    @property
    def ticks(self) -> tuple[float, ...]:
        """Return readable scale ticks within the channel's fixed display range.

        Returns:
            Readable scale ticks within the channel's fixed display range.
        """
        if self.unit == "°":
            return (0.0, 90.0, 180.0)
        if ceil(self.high) - floor(self.low) <= 12:
            return tuple(float(i) for i in range(ceil(self.low), floor(self.high) + 1))
        return tuple(sorted({self.low, -1.0, 0.0, 1.0, self.high}))


@dataclass(frozen=True, slots=True)
class ExportTimeline:
    """Export timeline contract and owned data.

    Attributes:
        source_sha256: SHA-256 identity of the original recording bytes.
        sample_rate: Effective source samples per second, retaining its origin separately.
        replay_origin: Source index used as replay time zero.
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
        smoothing_window: Odd number of source samples used for smoothing.
        channels: Prepared channels to inspect or display.
        settings: Validated settings controlling this operation.
        analysis: Prepared recording-analysis snapshot used by this operation.
    """

    source_sha256: str
    sample_rate: float
    replay_origin: int
    first: int
    last: int
    smoothing_window: int
    channels: tuple[ExportChannel, ...]
    settings: ExportSettings
    analysis: RecordingAnalysis

    def context_at(self, position: float) -> str:
        """Read the prepared full-history classification at the preceding source sample.

        Args:
            position: Fractional source-sample position.

        Returns:
            Prepared context label at the preceding source sample.

        Raises:
            ValueError: Position outside airtime context.
        """
        labels = self.analysis.context.labels
        if not isfinite(position) or not 0 <= position < len(self.analysis.time.source_indices):
            raise ValueError("Position outside airtime context")
        return labels[floor(position)].value.replace("_", " ").title() if labels else "Unavailable"

    @property
    def frame_count(self) -> int:
        # Include the last selected source sample's complete sample interval.
        """Return the rounded output-frame count including the final sample interval.

        Returns:
            The rounded output-frame count including the final sample interval.
        """
        return ceil(
            Fraction(self.last - self.first + 1)
            * self.settings.frame_rate
            / Fraction(str(self.sample_rate)),
        )

    def sample_position(self, frame: int) -> float:
        """Map an output frame index to its fractional source-sample position.

        Args:
            frame: Zero-based output video frame index.

        Returns:
            Fractional source-sample position corresponding to the output frame.

        Raises:
            ValueError: Frame outside export interval.
        """
        if not 0 <= frame < self.frame_count:
            raise ValueError("Frame outside export interval")
        return min(
            self.last,
            self.first + frame * self.sample_rate / float(self.settings.frame_rate),
        )

    def value_at(self, channel: ExportChannel, position: float) -> float | None:
        """Read or interpolate a channel value without bridging missing samples.

        Args:
            channel: Prepared channel whose units, bounds and availability govern the result.
            position: Fractional source-sample position.

        Returns:
            The channel value at the source position, or None when required samples are
            missing.
        """
        lower = max(self.first, min(self.last, floor(position)))
        upper = min(self.last, lower + 1)
        a, b = channel.values[lower], channel.values[upper]
        weight = position - lower
        if a is None or (weight > 0 and b is None):
            return None
        return a if b is None else a * (1 - weight) + b * weight


def prepare_export(
    analysis: RecordingAnalysis,
    settings: ExportSettings,
    first: int,
    last: int,
) -> ExportTimeline:
    """Bind prepared analysis and an inclusive interval into a video timeline.

    Args:
        analysis: Prepared recording-analysis snapshot used by this operation.
        settings: Validated settings controlling this operation.
        first: First included source sample index.
        last: Last included source sample index.

    Returns:
        Immutable video timeline bound to prepared analysis and source bounds.

    Raises:
        ValueError: Invalid export sample interval. If the supplied settings or operation
            state are invalid. Export requires a sample rate.
        AssertionError: If a required internal invariant does not hold.
    """
    count = len(analysis.time.source_indices)
    if type(first) is not int or type(last) is not int or not 0 <= first <= last < count:
        raise ValueError("Invalid export sample interval")
    forces = analysis.forces.smoothed
    if forces.channels is None:
        reason = forces.availability.reason
        raise ValueError(reason.message if reason else "Calibrated forces are unavailable")
    rate = analysis.time.basis.sample_rate
    if rate is None:
        raise ValueError("Export requires a sample rate")
    channels: list[ExportChannel] = []
    names = ("Vertical", "Lateral", "Longitudinal")
    colors = ("#8edce1", "#ebd36a", "#dba8e0")
    hints = ("Vertical force", "+ Right / − Left", "+ Acceleration / − Braking")
    for index, samples in enumerate(forces.channels):
        values = ExportValues(samples)
        selected = tuple(value for value in values[first : last + 1] if value is not None)
        low, high = min(-1.0, min(selected, default=-1.0)), max(1.0, max(selected, default=1.0))
        channels.append(
            ExportChannel(
                names[index],
                "g",
                colors[index],
                hints[index],
                values,
                low * 1.05,
                high * 1.05,
                settings.invert_vertical
                if index == 0
                else settings.invert_lateral
                if index == 1
                else False,
            ),
        )
    channels.append(
        ExportChannel(
            "Orientation",
            "°",
            "#e9a571",
            "Tilt relative to calibrated vertical",
            ExportValues(analysis.orientation.values)
            if analysis.orientation.values is not None
            else (None,) * count,
            0.0,
            180.0,
            False,
        ),
    )
    window = dict(analysis.configuration.smoothing.parameters).get("window_samples", 11)
    assert type(window) is int
    return ExportTimeline(
        analysis.source.source_sha256,
        rate.value,
        analysis.replay_origin,
        first,
        last,
        window,
        tuple(channels),
        settings,
        analysis,
    )
