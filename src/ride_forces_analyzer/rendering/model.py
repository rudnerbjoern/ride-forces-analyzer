"""Immutable export preparation, time mapping and display contracts; no widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.validation.checks import validate_sample_range

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from fractions import Fraction
from math import ceil, floor, isfinite
from typing import Annotated, Literal, overload

from pydantic import BaseModel, PlainSerializer, field_serializer

from ride_forces_analyzer import __version__
from ride_forces_analyzer.analysis.models import SampleValues
from ride_forces_analyzer.analysis.recording import AnalysisConfiguration, RecordingAnalysis
from ride_forces_analyzer.i18n import Language
from .layouts.contracts import LayoutPosition
from .layouts.contracts import ExportLayout as ExportLayout
from .layouts.contracts import ExportExtent as ExportExtent
from .layouts.contracts import VideoAspect as VideoAspect
from .scales import history_extent, lateral_scale, longitudinal_scale, selected_bounds


class VideoOutput(StrEnum):
    """Video output modes with stable identifiers for saved export settings.

    Attributes:
        TRANSPARENT: Overlay with alpha in a ProRes 4444 MOV, stored as ``transparent``.
        OPAQUE: Video on a black background in an H.264 MP4, stored as ``opaque``.
    """

    TRANSPARENT = "transparent"
    OPAQUE = "opaque"


class StandardFrameRate(StrEnum):
    """Standard video rates with exact encoder values and display labels.

    Attributes:
        FPS_23_976: Exact 24000/1001 frames per second, displayed as 23.976.
        FPS_24: 24 frames per second.
        FPS_25: 25 frames per second.
        FPS_30: 30 frames per second.
        FPS_50: 50 frames per second and the default for new exports.
        FPS_59_94: Exact 60000/1001 frames per second, displayed as 59.94.
        FPS_60: 60 frames per second.
    """

    FPS_23_976 = "24000/1001"
    FPS_24 = "24"
    FPS_25 = "25"
    FPS_30 = "30"
    FPS_50 = "50"
    FPS_59_94 = "60000/1001"
    FPS_60 = "60"

    @property
    def label(self) -> str:
        """Return the frame rate's display label.

        Returns:
            Rounded display label for fractional rates, otherwise the integer text.
        """
        if self is StandardFrameRate.FPS_23_976:
            return "23.976"
        return "59.94" if self is StandardFrameRate.FPS_59_94 else self.value

    @property
    def fraction(self) -> Fraction:
        """Return the exact video rate without rounding.

        Returns:
            Rational number of frames per second.
        """
        return Fraction(self.value)


FrameRate = int | StandardFrameRate
EXPORT_FRAME_RATES: tuple[StandardFrameRate, ...] = tuple(StandardFrameRate)
DEFAULT_FRAME_RATE = StandardFrameRate.FPS_50


def frame_rate_value(value: FrameRate) -> int | str:
    """Preserve existing preset and encoder metadata values.

    Args:
        value: Standard frame rate or validated custom integer rate.

    Returns:
        Integer for whole rates, or the exact fractional string for fractional rates.
    """
    if isinstance(value, StandardFrameRate):
        rate = value.fraction
        return rate.numerator if rate.denominator == 1 else value.value
    return value


PROFILES: tuple[tuple[ExportLayout, str], ...] = (
    (ExportLayout.RIBBON, "Flow Ribbon"),
    (ExportLayout.CORNERS, "Corner Instruments"),
    (ExportLayout.HUD, "HUD"),
    (ExportLayout.ORBIT, "G-Orbit"),
    (ExportLayout.COLUMN, "Four-panel column"),
)


@dataclass(frozen=True, slots=True)
class ExportSettings:
    """Export settings contract and owned data.

    Attributes:
        fps: StandardFrameRate member or custom integer from 1 to 120; standard
            integers are normalized to enum members, preserving exact fractional rates.
        window_seconds: Width of the visible source-time context in seconds.
        output: VideoOutput member selecting transparency, codec and container.
        invert_vertical: Whether the vertical plot uses the selected inverted display
            direction.
        invert_lateral: Whether the layout uses its supported lateral direction override.
        prefer_gpu: Whether encoding prefers a probed NVIDIA backend with CPU fallback.
        layout: ExportLayout member selecting the renderer; JSON retains its text key.
        aspect: VideoAspect member selecting the canvas; JSON retains its text value.
        language: Language member used for overlay text; saved JSON retains its text code.
        position: Requested source position or named layout placement, as declared by the
            type.
        extent: Typed output-area choice; defaults to the complete canvas.
    """

    fps: Annotated[FrameRate, PlainSerializer(frame_rate_value)] = DEFAULT_FRAME_RATE
    window_seconds: float = 12.0
    output: VideoOutput = VideoOutput.TRANSPARENT
    invert_vertical: bool = True
    invert_lateral: bool = True
    prefer_gpu: bool = True
    layout: ExportLayout = ExportLayout.COLUMN
    aspect: VideoAspect = VideoAspect.LANDSCAPE
    language: Language = Language.ENGLISH
    position: LayoutPosition | None = None
    extent: ExportExtent = ExportExtent.FULL_FRAME

    @property
    def dimensions(self) -> tuple[int, int]:
        """Return the layout's full-frame reference canvas dimensions.

        Returns:
            Full-frame width and height; resolve_geometry supplies extent-specific sizes.
        """
        from .layouts import canvas_dimensions

        return canvas_dimensions(self)

    @property
    def frame_rate(self) -> Fraction:
        """Return the exact encoder rate without rounding fractional frame rates.

        Returns:
            Exact output frames per second as a rational number.
        """
        return self.fps.fraction if isinstance(self.fps, StandardFrameRate) else Fraction(self.fps)

    @property
    def fps_label(self) -> str:
        """Return the display label for an integer or supported fractional frame rate.

        Returns:
            Integer rate text, or 23.976/59.94 for the corresponding exact fraction.
        """
        return self.fps.label if isinstance(self.fps, StandardFrameRate) else str(self.fps)

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Unsupported overlay language. Unknown export aspect ratio. Frame rate
                must be an integer from 1 to 120, 24000/1001 or 60000/1001. Visible time window must be
                from 1 to 60 seconds. Unknown export output mode/layout, unsupported extent
                or placement, or output dimensions incompatible with supported codecs.
        """
        if type(self.language) is not Language:
            raise ValueError("Unsupported overlay language")
        if type(self.aspect) is not VideoAspect:
            raise ValueError("Unknown export aspect ratio")
        if type(self.fps) is not StandardFrameRate and not (
            type(self.fps) is int and 1 <= self.fps <= 120
        ):
            raise ValueError(
                "Frame rate must be an integer from 1 to 120, 24000/1001 or 60000/1001",
            )
        if type(self.fps) is int:
            try:
                standard = StandardFrameRate(str(self.fps))
            except ValueError:
                pass  # Custom integer rates remain integers.
            else:
                object.__setattr__(self, "fps", standard)
        if not isfinite(self.window_seconds) or not 1 <= self.window_seconds <= 60:
            raise ValueError("Visible time window must be from 1 to 60 seconds")
        if type(self.output) is not VideoOutput:
            raise ValueError("Unknown export output mode")
        if type(self.layout) is not ExportLayout:
            raise ValueError("Unknown export layout")
        from .layouts.registry import resolve_geometry

        resolve_geometry(self)


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
    def reference(self) -> float:
        """Return the absolute neutral force level: 1 g vertically, zero otherwise.

        Returns:
            Neutral value in the channel's displayed units; original samples are unchanged.
        """
        return 1.0 if self.name == "Vertical" and self.unit == "g" else 0.0

    @property
    def ticks(self) -> tuple[float, ...]:
        """Return readable scale ticks within the channel's fixed display range.

        Returns:
            Readable scale ticks within the channel's fixed display range.
        """
        if self.unit == "°":
            return (0.0, 90.0, 180.0)
        if self.name in ("Lateral", "Longitudinal"):
            scale = lateral_scale if self.name == "Lateral" else longitudinal_scale
            _, _, step = scale(max(abs(self.low), abs(self.high)))
            return tuple(
                sorted(
                    {self.low, self.high, 0.0}
                    | {
                        index * step
                        for index in range(ceil(self.low / step), floor(self.high / step) + 1)
                    },
                ),
            )
        if ceil(self.high) - floor(self.low) <= 12:
            ticks = {float(i) for i in range(ceil(self.low), floor(self.high) + 1)}
        else:
            ticks = {self.low, -1.0, 0.0, 1.0, self.high}
        if self.name == "Vertical":
            ticks.update((self.low, self.high, self.reference))
            ticks = {tick for tick in ticks if self.low <= tick <= self.high}
        return tuple(sorted(ticks))


def analysis_configuration_metadata(configuration: AnalysisConfiguration) -> dict[str, object]:
    """Serialize a complete analysis recipe without computed sample buffers.

    Args:
        configuration: Effective immutable analysis configuration to describe.

    Returns:
        JSON-compatible recipe, including frozen profile mappings and calibration.
    """
    profile = configuration.profile
    return {
        "profile": {
            "name": profile.name,
            "schema_version": profile.schema_version,
            "configuration": dict(profile.configuration),
            "policy_references": profile.policy_references,
            "assumptions": profile.assumptions,
            "allow_provisional": profile.allow_provisional,
        },
        "projection": asdict(configuration.projection),
        "smoothing": asdict(configuration.smoothing),
        "orientation": asdict(configuration.orientation),
        "context": asdict(configuration.context),
        "events": asdict(configuration.events) if configuration.events is not None else None,
        "context_input": configuration.context_input,
        "events_input": configuration.events_input,
        "ride_bounds": configuration.ride_bounds,
        "calibration": asdict(configuration.calibration),
    }


class ExportSnapshot(BaseModel, frozen=True, strict=True):
    """Own the effective settings and analysis recipe of any prepared video export.

    Attributes:
        schema_version: Version of the serialized export snapshot.
        application_version: Analyzer version preparing the export.
        source_sha256: Identity of the original recording bytes.
        settings: Complete visual and encoding preferences bound to the export.
        analysis_configuration: Effective recipe of the prepared analysis, not raw data.
        sample_rate: Effective source samples per second.
        first_sample: First included source index.
        last_sample_inclusive: Last included source index.
        replay_origin: Source index used as replay time zero.
        smoothing_window: Effective smoothing window in source samples.
        output_dimensions: Resolved output width and height in pixels.
        planned_frame_count: Prepared output frame count, not encoded completion.
    """

    schema_version: Literal[1] = 1
    application_version: str = __version__
    source_sha256: str
    settings: ExportSettings
    analysis_configuration: AnalysisConfiguration
    sample_rate: float
    first_sample: int
    last_sample_inclusive: int
    replay_origin: int
    smoothing_window: int
    output_dimensions: tuple[int, int]
    planned_frame_count: int

    @field_serializer("analysis_configuration")
    def serialize_configuration(self, value: AnalysisConfiguration) -> dict[str, object]:
        """Serialize the bound recipe using the common export representation.

        Args:
            value: Effective configuration stored by this snapshot.

        Returns:
            JSON-compatible analysis recipe without computed sample buffers.
        """
        return analysis_configuration_metadata(value)


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
        snapshot: Export-owned settings and recipe shared by single and batch outputs.
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
    snapshot: ExportSnapshot = field(init=False)

    def __post_init__(self) -> None:
        """Capture export metadata from this timeline's effective bound analysis.

        Returns:
            None.

        Raises:
            ValueError: Bound settings do not resolve to supported output geometry.
        """
        from .layouts import resolve_geometry

        object.__setattr__(
            self,
            "snapshot",
            ExportSnapshot(
                source_sha256=self.source_sha256,
                settings=self.settings,
                analysis_configuration=self.analysis.configuration,
                sample_rate=self.sample_rate,
                first_sample=self.first,
                last_sample_inclusive=self.last,
                replay_origin=self.replay_origin,
                smoothing_window=self.smoothing_window,
                output_dimensions=resolve_geometry(self.settings).output_size,
                planned_frame_count=self.frame_count,
            ),
        )

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
    validate_sample_range(first, last, count, "Invalid export sample interval")
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
        reference = 1.0 if index == 0 else 0.0
        low, high = selected_bounds(values, first, last, reference)
        if index == 0:
            extent = history_extent(max(abs(low - reference), abs(high - reference)))
            low, high = reference - extent, reference + extent
        elif index == 1:
            low, high, _ = lateral_scale(max(abs(low), abs(high)))
        else:
            low, high, _ = longitudinal_scale(max(abs(low), abs(high)))
        channels.append(
            ExportChannel(
                names[index],
                "g",
                colors[index],
                hints[index],
                values,
                low,
                high,
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
