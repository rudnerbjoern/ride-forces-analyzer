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
from ride_forces_analyzer.i18n import Language

FrameRate = int | Literal["60000/1001"]
EXPORT_FRAME_RATES: tuple[FrameRate, ...] = (24, 25, 30, 50, "60000/1001", 60)

ExportLayout = Literal["column", "ribbon", "corners", "capsule", "orbit"]
PROFILES: tuple[tuple[ExportLayout, str], ...] = (
    ("ribbon", "Flow Ribbon"),
    ("corners", "Corner Instruments"),
    ("capsule", "Telemetry Capsule"),
    ("orbit", "G-Orbit"),
    ("column", "Four-panel column"),
)


@dataclass(frozen=True, slots=True)
class ExportSettings:
    fps: FrameRate = 50
    window_seconds: float = 12.0
    output: Literal["transparent", "opaque"] = "transparent"
    invert_vertical: bool = True
    invert_lateral: bool = True
    prefer_gpu: bool = True
    layout: ExportLayout = "column"
    aspect: Literal["landscape", "portrait"] = "landscape"
    language: Language = "en"

    @property
    def dimensions(self) -> tuple[int, int]:
        return (2160, 3840) if self.aspect == "portrait" else (3840, 2160)

    @property
    def frame_rate(self) -> Fraction:
        """Exact encoder rate; retain the fractional ratio rather than rounding to 59.94."""
        return Fraction(self.fps)

    @property
    def fps_label(self) -> str:
        return "59.94" if self.fps == "60000/1001" else str(self.fps)

    def __post_init__(self) -> None:
        if self.language not in ("en", "de"):
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


@dataclass(frozen=True, slots=True)
class ExportValues(Sequence[float | None]):
    """Read-only scalar view of a shared stage buffer; invalid rows remain None."""

    samples: SampleValues

    def __len__(self) -> int:
        return len(self.samples.valid_rows)

    @overload
    def __getitem__(self, index: int) -> float | None: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[float | None, ...]: ...

    def __getitem__(self, index: int | slice) -> float | None | tuple[float | None, ...]:
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(len(self))))
        return float(self.samples.values[index]) if self.samples.valid_rows[index] else None


def prepare_export_analysis(
    analysis: RecordingAnalysis,
    configuration: AnalysisConfiguration,
) -> RecordingAnalysis:
    """Bind matching work or recalculate only changed stages, without changing the source."""
    if configuration == analysis.configuration:
        return analysis
    return analysis.with_configuration(
        configuration,
        revision=analysis.revision + 1,
        calculation_time=datetime.now(UTC),
    )


@dataclass(frozen=True, slots=True)
class ExportChannel:
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
        if self.unit == "°":
            return (0.0, 90.0, 180.0)
        if ceil(self.high) - floor(self.low) <= 12:
            return tuple(float(i) for i in range(ceil(self.low), floor(self.high) + 1))
        return tuple(sorted({self.low, -1.0, 0.0, 1.0, self.high}))


@dataclass(frozen=True, slots=True)
class ExportTimeline:
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
        """Read the prepared full-history classification at the preceding source sample."""
        labels = self.analysis.context.labels
        if not isfinite(position) or not 0 <= position < len(self.analysis.time.source_indices):
            raise ValueError("Position outside airtime context")
        return labels[floor(position)].value.replace("_", " ").title() if labels else "Unavailable"

    @property
    def frame_count(self) -> int:
        # Include the last selected source sample's complete sample interval.
        return ceil(
            Fraction(self.last - self.first + 1)
            * self.settings.frame_rate
            / Fraction(str(self.sample_rate)),
        )

    def sample_position(self, frame: int) -> float:
        if not 0 <= frame < self.frame_count:
            raise ValueError("Frame outside export interval")
        return min(
            self.last,
            self.first + frame * self.sample_rate / float(self.settings.frame_rate),
        )

    def value_at(self, channel: ExportChannel, position: float) -> float | None:
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
        analysis.time.replay_origin,
        first,
        last,
        window,
        tuple(channels),
        settings,
        analysis,
    )
