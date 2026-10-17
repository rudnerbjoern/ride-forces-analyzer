"""Qt-independent raw-recording presentation and local sample-selection contracts."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from importlib.util import find_spec
from typing import TYPE_CHECKING
from math import ceil, floor, isclose, isfinite
from pathlib import Path

from ride_forces_analyzer.force_extrema import SelectionExtrema, calculate_extrema
from ride_forces_analyzer.domain import SourceNumber
from ride_forces_analyzer.importers import ImportFailure, ImportSuccess, import_forces

if TYPE_CHECKING:
    from ride_forces_analyzer.analysis.reference import AppReference


def format_sample_time(offset: int, rate: float) -> str:
    """MM:SS.ff uses a sample counter; fractional rates retain explicit seconds."""
    if not rate.is_integer():
        return f"{offset / rate:.3f} s"
    whole, frame = divmod(abs(offset), int(rate))
    minutes, seconds = divmod(whole, 60)
    width = max(2, len(str(int(rate) - 1)))
    sign = "-" if offset < 0 else ""
    return f"{sign}{minutes:02}:{seconds:02}.{frame:0{width}}"


@dataclass(frozen=True, slots=True)
class SampleRange:
    """Inclusive local selection; unrelated to source marker slicing semantics."""

    first: int
    last: int

    @property
    def count(self) -> int:
        return self.last - self.first + 1


@dataclass(frozen=True, slots=True)
class ExplorerData:
    source: ImportSuccess
    channels: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
    title: str
    summary: str
    notes: str
    value_range: tuple[float, float]
    reference: "AppReference | None" = None
    reference_enabled: bool = False
    reference_error: str | None = None

    @property
    def plotted_channels(self) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        return (
            self.reference.channels if self.reference_enabled and self.reference else self.channels
        )

    @property
    def channel_names(self) -> tuple[str, str, str]:
        return (
            (
                "Vertical",
                "Lateral (+ right / − left)",
                "Longitudinal (+ acceleration / − braking)",
            )
            if self.reference_enabled
            else ("x", "y", "z")
        )

    def with_reference(self, enabled: bool) -> "ExplorerData":
        active = enabled and self.reference is not None
        channels = self.reference.channels if active and self.reference else self.channels
        low = min(0.0, min(min(axis) for axis in channels))
        high = max(0.0, max(max(axis) for axis in channels))
        bounds = (low * 1.05, high * 1.05) if low < high else (-1.0, 1.0)
        if active:
            bounds = (min(-1.05, bounds[0]), max(1.05, bounds[1]))
        return replace(self, reference_enabled=active, value_range=bounds)

    @property
    def value_ticks(self) -> tuple[float, ...]:
        low, high = self.value_range
        if self.reference_enabled and floor(high) - ceil(low) <= 20:
            ticks = {float(value) for value in range(ceil(low), floor(high) + 1)}
        else:
            ticks = {low * (1 - step / 4) + high * (step / 4) for step in range(5)}
        if self.reference_enabled:
            ticks.update((-1.0, 0.0, 1.0))
        return tuple(sorted(ticks))

    @property
    def smoothing_text(self) -> str:
        window = self.reference.smoothing_window if self.reference else 11
        if window == 1:
            return "1 sample • Smoothing off"
        half_ms = (window // 2) / self.sample_rate * 1000
        return f"{window} samples • ±{half_ms:g} ms • Centered mean"

    def with_smoothing(self, window: int) -> "ExplorerData":
        if self.reference is None:
            return self
        from ride_forces_analyzer.analysis.reference import smooth_reference

        reference = smooth_reference(self.reference, window, calculation_time=datetime.now(UTC))
        return replace(self, reference=reference).with_reference(self.reference_enabled)

    @property
    def metadata_fields(self) -> tuple[tuple[str, str], ...]:
        recording = self.source.recording
        fields = [
            ("Ride", recording.metadata.name),
            ("Park", recording.metadata.location),
        ]
        for label in ("Train", "Row", "Seat"):
            for attribute in recording.attributes:
                if attribute.label.casefold() == label.casefold():
                    value = attribute.value
                    if isinstance(value, SourceNumber):
                        fields.append((label, value.token))
                    elif isinstance(value, str):
                        fields.append((label, value))
        return tuple((label, value) for label, value in fields if value and value.strip())

    @property
    def metadata_text(self) -> str:
        return "  |  ".join(f"{label}: {value}" for label, value in self.metadata_fields)

    @property
    def metadata_rows_text(self) -> str:
        return "\n".join(f"{label}: {value}" for label, value in self.metadata_fields)

    @property
    def overview_text(self) -> str:
        recording = self.source.recording
        return f"{recording.metadata.device or 'Unknown device'} · {self.count:,} samples · {self.sample_rate:g} Hz"

    @property
    def availability_text(self) -> str:
        gravity = "available" if self.source.recording.motion.gravity is not None else "absent"
        return f"Gravity {gravity} · GPS {self.source.recording.gps_status.value} · Inferred time"

    def sample_clock_text(self, index: int) -> str:
        self.select(index, index)
        return f"Replay {self.replay_text(index)} · Recording {self.time_at(index):.3f} s · {self.sample_rate:g} Hz"

    def sample_cards(self, index: int) -> tuple[tuple[str, str, str], ...]:
        self.select(index, index)
        cards: list[tuple[str, str, str]] = []
        for axis, (name, values) in enumerate(
            zip(self.channel_names, self.plotted_channels, strict=True),
        ):
            value = values[index]
            if self.reference_enabled:
                meanings = (
                    ("Vertical force", "Vertical force"),
                    ("Left", "Right"),
                    ("Braking", "Acceleration"),
                )
                meaning = "Neutral" if value == 0 else meanings[axis][int(value > 0)]
                cards.append((name.partition(" (")[0], f"{value:+.2f} g", meaning))
            else:
                cards.append((name, f"{value:.6g}", "Unit unknown"))
        return tuple(cards)

    def selection_extrema(self, first: int, last: int) -> SelectionExtrema:
        return calculate_extrema(
            self.source,
            first,
            last,
            reference=self.reference if self.reference_enabled else None,
        )

    def extrema_text(self, first: int, last: int) -> tuple[str, tuple[str, ...]]:
        result = self.selection_extrema(first, last)
        context = (
            f"Calibrated · {result.smoothing_window} samples smoothing · g"
            if result.mode == "calibrated"
            else "Raw source · Unfiltered · Unit unknown"
        )
        rows: list[str] = []
        for channel in result.channels:
            points: list[str] = []
            for label, point in (("Min", channel.minimum), ("Max", channel.maximum)):
                value = f"{point.value:+.2f} g" if result.unit == "g" else f"{point.value:.6g}"
                points.append(
                    f"{label} {value} · Replay {self.replay_text(point.index)}\n"
                    f"Sample {point.index} · Recording {point.recording_seconds:.3f} s",
                )
            rows.append(f"{channel.name}\n" + "\n".join(points))
        return f"{context} · {result.sample_rate:g} Hz · {result.count:,} selected", tuple(rows)

    @property
    def count(self) -> int:
        return len(self.channels[0])

    @property
    def markers(self) -> tuple[tuple[str, int], ...]:
        indices = self.source.recording.indices
        return tuple(
            (name, index)
            for name, index in (
                ("startIndex", indices.start),
                ("endIndex", indices.end),
                ("gravityIndex", indices.gravity),
                ("inclineIndex", indices.incline),
            )
            if index is not None
            and (
                self.source.recording.source.root is None
                or name in self.source.recording.source.root
            )
        )

    @property
    def default_time_range(self) -> tuple[float, float]:
        indices = self.source.recording.indices
        low, high = self.time_at(indices.start), self.time_at(indices.end)
        if low == high:
            low = max(0.0, min(low, self.duration - 1 / self.sample_rate))
            high = min(self.duration, low + 1 / self.sample_rate)
        return low, high

    @property
    def sample_rate(self) -> float:
        return self.source.recording.motion.sample_rate.value

    @property
    def duration(self) -> float:
        """Elapsed time of the final sample, not an extra acquisition interval."""
        return self.time_at(self.count - 1)

    @property
    def replay_time_label(self) -> str:
        return (
            f"Replay time (MM:SS.ff @ {self.sample_rate:g} Hz; ff = sample)"
            if self.sample_rate.is_integer()
            else f"Replay time (s @ {self.sample_rate:g} Hz)"
        )

    def replay_text(self, index: int) -> str:
        self.select(index, index)
        return format_sample_time(index - self.source.recording.indices.start, self.sample_rate)

    def time_at(self, index: int) -> float:
        self.select(index, index)
        return index / self.sample_rate

    def select(self, first: int, last: int) -> SampleRange:
        if type(first) is not int or type(last) is not int or not 0 <= first <= last < self.count:
            raise ValueError("Selection requires bounded, ordered sample indices")
        return SampleRange(first, last)

    def select_visible(self, low: float, high: float) -> SampleRange:
        if not isfinite(low) or not isfinite(high) or low > high:
            raise ValueError("Visible range must be finite and ordered")

        def sample_coordinate(seconds: float) -> float:
            coordinate = min(float(self.count - 1), max(0.0, seconds * self.sample_rate))
            nearest = round(coordinate)
            # Avoid selecting an adjacent sample solely due to float round-trip error.
            return (
                float(nearest)
                if isclose(coordinate, nearest, rel_tol=0, abs_tol=1e-9)
                else coordinate
            )

        first = floor(sample_coordinate(low))
        last = ceil(sample_coordinate(high))
        return self.select(first, last)

    def sample_text(self, index: int) -> str:
        self.select(index, index)
        values = "   ".join(
            f"{name} {axis[index]:.6g}"
            for name, axis in zip(self.channel_names, self.plotted_channels, strict=True)
        )
        return (
            f"Sample {index:,}   |   Replay {self.replay_text(index)} @ {self.sample_rate:g} Hz"
            f"   |   Recording {self.time_at(index):.3f} s   |   {values}"
        )


def present_recording(source: ImportSuccess) -> ExplorerData:
    recording = source.recording
    motion = recording.motion
    channels = (
        tuple(vector.x for vector in motion.acceleration),
        tuple(vector.y for vector in motion.acceleration),
        tuple(vector.z for vector in motion.acceleration),
    )
    name = recording.metadata.name
    path = recording.source.provenance.path
    title = name or (path.stem if path is not None else "Recording")
    device = recording.metadata.device or "Unknown device"
    gravity = "available" if motion.gravity is not None else "absent"
    gps = recording.gps_status.value
    rate = motion.sample_rate
    summary = (
        f"{device}  |  {len(motion.acceleration):,} samples  |  "
        f"Sample rate {rate.value:g} Hz ({rate.origin.value})  |  Time: INFERRED_UNIFORM  |  Gravity {gravity}  |  GPS {gps}"
    )
    notes = (
        "\n".join(
            f"{item.severity.value.upper()} {item.code} {item.json_path}: {item.message}"
            for item in source.diagnostics
        )
        or "No import diagnostics."
    )
    low = min(0.0, min(min(axis) for axis in channels))
    high = max(0.0, max(max(axis) for axis in channels))
    # Pad each signed extremum independently; keep zero visible for one-sided data.
    value_range = (low * 1.05, high * 1.05) if low < high else (-1.0, 1.0)
    if not all(isfinite(value) for value in value_range):
        raise ValueError("Source values exceed the chart display range")
    reference = None
    reference_error = None
    if find_spec("numpy") is not None:
        from ride_forces_analyzer.analysis.reference import reconstruct_app_reference

        try:
            reference = reconstruct_app_reference(source, calculation_time=datetime.now(UTC))
        except ValueError as error:
            reference_error = str(error)
    else:
        reference_error = "The optional NumPy analysis package is not installed"
    if reference_error:
        notes += f"\nCALIBRATION_UNAVAILABLE: {reference_error}. Raw recording remains available."
    return ExplorerData(
        source,
        channels,
        title,
        summary,
        notes,
        value_range,
        reference=reference,
        reference_error=reference_error,
    )


def load_recording(path: Path) -> ExplorerData | ImportFailure:
    """Read an original using M2; keep source ownership and all warnings intact."""
    source = import_forces(path)
    return source if isinstance(source, ImportFailure) else present_recording(source)


def failure_text(failure: ImportFailure) -> str:
    """Bounded field-oriented feedback, never an exception or recording payload."""
    items = failure.diagnostics[:5]
    return "Could not open recording. " + "; ".join(
        f"{item.code}: {item.message}" for item in items
    )
