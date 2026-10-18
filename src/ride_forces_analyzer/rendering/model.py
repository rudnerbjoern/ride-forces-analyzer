"""Immutable export preparation, time mapping and display contracts; no widgets."""

from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor, isfinite
from typing import Literal

from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.i18n import Language

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
    fps: int = 50
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

    def __post_init__(self) -> None:
        if self.language not in ("en", "de"):
            raise ValueError("Unsupported overlay language")
        if self.aspect not in ("landscape", "portrait"):
            raise ValueError("Unknown export aspect ratio")
        if type(self.fps) is not int or not 1 <= self.fps <= 120:
            raise ValueError("Frame rate must be an integer from 1 to 120")
        if not isfinite(self.window_seconds) or not 1 <= self.window_seconds <= 60:
            raise ValueError("Visible time window must be from 1 to 60 seconds")
        if self.output not in ("transparent", "opaque"):
            raise ValueError("Unknown export output mode")
        if self.layout not in tuple(key for key, _ in PROFILES):
            raise ValueError("Unknown export layout")


@dataclass(frozen=True, slots=True)
class ExportChannel:
    name: str
    unit: str
    color: str
    hint: str
    values: tuple[float | None, ...]
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

    @property
    def frame_count(self) -> int:
        # Include the last selected source sample's complete sample interval.
        return ceil(
            Fraction(self.last - self.first + 1)
            * self.settings.fps
            / Fraction(str(self.sample_rate)),
        )

    def sample_position(self, frame: int) -> float:
        if not 0 <= frame < self.frame_count:
            raise ValueError("Frame outside export interval")
        return min(self.last, self.first + frame * self.sample_rate / self.settings.fps)

    def value_at(self, channel: ExportChannel, position: float) -> float | None:
        lower = max(self.first, min(self.last, floor(position)))
        upper = min(self.last, lower + 1)
        a, b = channel.values[lower], channel.values[upper]
        weight = position - lower
        if a is None or (weight > 0 and b is None):
            return None
        return a if b is None else a * (1 - weight) + b * weight


def prepare_export(
    data: ExplorerData,
    settings: ExportSettings,
    first: int,
    last: int,
) -> ExportTimeline:
    data.select(first, last)
    reference = data.reference
    if reference is None:
        raise ValueError(data.reference_error or "Calibrated forces are unavailable")
    channels: list[ExportChannel] = []
    names = ("Vertical", "Lateral", "Longitudinal")
    colors = ("#8edce1", "#ebd36a", "#dba8e0")
    hints = ("Vertical force", "+ Right / − Left", "+ Acceleration / − Braking")
    for index, values in enumerate(reference.channels):
        selected = values[first : last + 1]
        low, high = min(-1.0, min(selected)), max(1.0, max(selected))
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
            orientation_degrees(data.source.recording),
            0.0,
            180.0,
            False,
        ),
    )
    return ExportTimeline(
        data.source.source_sha256,
        data.sample_rate,
        data.source.recording.indices.start,
        first,
        last,
        reference.smoothing_window,
        tuple(channels),
        settings,
    )
