"""Qt-independent raw-recording presentation and local sample-selection contracts.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words cellspacing

from ride_forces_analyzer.i18n import diagnostic_message, get_language, tr

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from html import escape
from importlib.util import find_spec
from typing import TYPE_CHECKING
from math import ceil, floor, isclose, isfinite
from pathlib import Path

from ride_forces_analyzer.force_extrema import SelectionExtrema, calculate_extrema
from ride_forces_analyzer.domain import SourceNumber
from ride_forces_analyzer.importers import ImportFailure, ImportSuccess, import_forces


def _details_table(rows: tuple[tuple[str, str], ...]) -> str:
    return (
        '<table width="100%" cellspacing="0" cellpadding="2">'
        + "".join(
            f'<tr><td valign="top">{escape(label)}</td>'
            f'<td align="right" valign="top">{escape(value)}</td></tr>'
            for label, value in rows
        )
        + "</table>"
    )


if TYPE_CHECKING:
    from ride_forces_analyzer.analysis.reference import AppReference
    from ride_forces_analyzer.analysis.airtime import AirtimeContext


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
    airtime_context: "AirtimeContext | None" = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        context = None
        if self.reference is not None:
            from ride_forces_analyzer.analysis.airtime import AirtimeContext

            context = AirtimeContext.prepare(self.reference.channels[0], self.sample_rate)
        object.__setattr__(self, "airtime_context", context)

    @property
    def localized_notes(self) -> str:
        if get_language() == "en":
            return self.notes
        lines = [
            f"{item.severity.value.upper()} {item.code} {item.json_path}: "
            f"{diagnostic_message(item.code, item.message)}"
            for item in self.source.diagnostics
        ]
        if self.reference_error:
            lines.append(f"CALIBRATION_UNAVAILABLE: {tr(self.reference_error)}")
        return "\n".join(lines) or tr("No import diagnostics.")

    @property
    def plotted_channels(self) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        return (
            self.reference.channels if self.reference_enabled and self.reference else self.channels
        )

    @property
    def channel_names(self) -> tuple[str, str, str]:
        return (
            (
                tr("Vertical"),
                tr("Lateral (+ right / − left)"),
                tr("Longitudinal (+ acceleration / − braking)"),
            )
            if self.reference_enabled
            else ("x", "y", "z")
        )

    @property
    def vertical_context_segments(self) -> tuple[tuple[str, int, int], ...]:
        """Inclusive drawing ranges sharing boundary points, only for calibrated g."""
        if not self.reference_enabled or self.airtime_context is None:
            return ()
        labels = self.airtime_context.labels
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
            return tr("1 sample • Smoothing off")
        half_ms = (window // 2) / self.sample_rate * 1000
        return tr("{0} samples • ±{1:g} ms • Centered mean", window, half_ms)

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
        return "  |  ".join(f"{tr(label)}: {value}" for label, value in self.metadata_fields)

    @property
    def metadata_rows_text(self) -> str:
        return "\n".join(f"{tr(label)}: {value}" for label, value in self.metadata_fields)

    @property
    def overview_text(self) -> str:
        recording = self.source.recording
        return tr(
            "{0} · {1:,} samples · {2:g} Hz",
            recording.metadata.device or tr("Unknown device"),
            self.count,
            self.sample_rate,
        )

    @property
    def availability_text(self) -> str:
        gravity = (
            tr("available") if self.source.recording.motion.gravity is not None else tr("absent")
        )
        return tr(
            "Gravity {0} · GPS {1} · Inferred time",
            gravity,
            tr(self.source.recording.gps_status.value),
        )

    def sample_clock_text(self, index: int) -> str:
        self.select(index, index)
        return tr(
            "Replay {0} · Recording {1:.3f} s · {2:g} Hz",
            self.replay_text(index),
            self.time_at(index),
            self.sample_rate,
        )

    def sample_cards(self, index: int) -> tuple[tuple[str, str, str], ...]:
        self.select(index, index)
        cards: list[tuple[str, str, str]] = []
        for axis, (name, values) in enumerate(
            zip(self.channel_names, self.plotted_channels, strict=True),
        ):
            value = values[index]
            if self.reference_enabled:
                meanings = (
                    (tr("Vertical force"), tr("Vertical force")),
                    (tr("Left"), tr("Right")),
                    (tr("Braking"), tr("Acceleration")),
                )
                meaning = tr("Neutral") if value == 0 else meanings[axis][int(value > 0)]
                if axis == 0 and self.airtime_context is not None:
                    meaning = tr(self.airtime_context.at(index))
                cards.append((name.partition(" (")[0], tr("{0:+.2f} g", value), meaning))
            else:
                cards.append((name, tr("{0:.6g}", value), tr("Unit unknown")))
        return tuple(cards)

    def selection_extrema(self, first: int, last: int) -> SelectionExtrema:
        return calculate_extrema(
            self.source,
            first,
            last,
            reference=self.reference if self.reference_enabled else None,
        )

    def extrema_text(
        self,
        first: int,
        last: int,
        *,
        rich: bool = False,
    ) -> tuple[str, tuple[str, ...]]:
        result = self.selection_extrema(first, last)
        context = (
            tr("Calibrated · {0} samples smoothing · g", result.smoothing_window)
            if result.mode == "calibrated"
            else tr("Raw source · Unfiltered · Unit unknown")
        )
        rows: list[str] = []
        for channel in result.channels:
            points: list[str] = []
            table_rows: list[str] = []
            for label, point in ((tr("Min"), channel.minimum), (tr("Max"), channel.maximum)):
                value = (
                    tr("{0:+.2f} g", point.value)
                    if result.unit == "g"
                    else tr("{0:.6g}", point.value)
                )
                points.append(
                    tr(
                        "{0} {1} · Replay {2}\nSample {3} · Recording {4:.3f} s",
                        label,
                        value,
                        self.replay_text(point.index),
                        point.index,
                        point.recording_seconds,
                    ),
                )
                details = tr(
                    "Sample {0} · Recording {1:.3f} s",
                    point.index,
                    point.recording_seconds,
                )
                table_rows.append(
                    f'<tr><td>{escape(label)}</td><td align="right"><b>{escape(value)}</b></td>'
                    f'<td align="right">{escape(self.replay_text(point.index))}</td></tr>'
                    f'<tr><td colspan="3"><small>{escape(details)}</small></td></tr>',
                )
            rows.append(
                '<table width="100%" cellspacing="0" cellpadding="2">'
                f'<tr><th colspan="2" align="left">{escape(tr(channel.name))}</th>'
                f'<td align="right">{escape(tr("Replay"))}</td></tr>'
                + "".join(table_rows)
                + "</table>"
                if rich
                else f"{tr(channel.name)}\n" + "\n".join(points),
            )
        return tr(
            "{0} · {1:g} Hz · {2:,} selected",
            context,
            result.sample_rate,
            result.count,
        ), tuple(rows)

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
            tr("Replay time (MM:SS.ff @ {0:g} Hz; ff = sample)", self.sample_rate)
            if self.sample_rate.is_integer()
            else tr("Replay time (s @ {0:g} Hz)", self.sample_rate)
        )

    def replay_text(self, index: int) -> str:
        self.select(index, index)
        return format_sample_time(index - self.source.recording.indices.start, self.sample_rate)

    def time_at(self, index: int) -> float:
        self.select(index, index)
        return index / self.sample_rate

    def sample_at_time(self, seconds: float) -> int:
        """Return the nearest sample, clamped to the recording bounds."""
        if not isfinite(seconds):
            raise ValueError("Sample time must be finite")
        return round(min(self.count - 1, max(0.0, seconds * self.sample_rate)))

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

    @property
    def technical_summary(self) -> str:
        recording = self.source.recording
        rate = recording.motion.sample_rate
        rows = (
            (tr("Device"), recording.metadata.device or tr("Unknown device")),
            (tr("Samples"), tr("{0:,}", self.count)),
            (tr("Sample rate"), tr("{0:g} Hz ({1})", rate.value, rate.origin.value)),
            (tr("Time basis"), "INFERRED_UNIFORM"),
            (
                tr("Gravity"),
                tr("available") if recording.motion.gravity is not None else tr("absent"),
            ),
            ("GPS", tr(recording.gps_status.value)),
        )
        return _details_table(rows)

    def sample_text(self, index: int, *, rich: bool = False) -> str:
        self.select(index, index)
        if rich:
            rows = (
                (tr("Sample"), tr("{0:,}", index)),
                (tr("Replay"), tr("{0} @ {1:g} Hz", self.replay_text(index), self.sample_rate)),
                (tr("Recording"), tr("{0:.3f} s", self.time_at(index))),
                *(
                    (name, tr("{0:.6g}", axis[index]))
                    for name, axis in zip(
                        self.channel_names,
                        self.plotted_channels,
                        strict=True,
                    )
                ),
            )
            return _details_table(rows)
        values = "   ".join(
            tr("{0} {1:.6g}", name, axis[index])
            for name, axis in zip(self.channel_names, self.plotted_channels, strict=True)
        )
        return tr(
            "Sample {0:,}   |   Replay {1} @ {2:g} Hz   |   Recording {3:.3f} s   |   {4}",
            index,
            self.replay_text(index),
            self.sample_rate,
            self.time_at(index),
            values,
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
    title = name or (path.stem if path is not None else tr("Recording"))
    device = recording.metadata.device or tr("Unknown device")
    gravity = tr("available") if motion.gravity is not None else tr("absent")
    gps = tr(recording.gps_status.value)
    rate = motion.sample_rate
    summary = tr(
        "{0}  |  {1:,} samples  |  Sample rate {2:g} Hz ({3})  |  Time: INFERRED_UNIFORM  |  Gravity {4}  |  GPS {5}",
        device,
        len(motion.acceleration),
        rate.value,
        rate.origin.value,
        gravity,
        gps,
    )
    notes = "\n".join(
        f"{item.severity.value.upper()} {item.code} {item.json_path}: {item.message}"
        for item in source.diagnostics
    ) or tr("No import diagnostics.")
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
        reference_error = tr("The optional NumPy analysis package is not installed")
    if reference_error:
        notes += tr(
            "\nCALIBRATION_UNAVAILABLE: {0}. Raw recording remains available.",
            reference_error,
        )
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
    return tr("Could not open recording. ") + "; ".join(
        f"{item.code}: {diagnostic_message(item.code, item.message)}" for item in items
    )
