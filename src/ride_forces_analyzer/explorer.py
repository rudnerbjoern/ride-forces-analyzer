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
from ride_forces_analyzer.domain import RecordingFormat, SourceNumber
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
    import numpy as np
    from numpy.typing import NDArray

    type PlotChannel = tuple[float, ...] | NDArray[np.float64]
    from ride_forces_analyzer.analysis.recording import RecordingAnalysis


def _import_notes(source: ImportSuccess, error: str | None) -> str:
    notes = "\n".join(
        f"{item.severity.value.upper()} {item.code} {item.json_path}: {item.message}"
        for item in source.diagnostics
    ) or tr("No import diagnostics.")
    if error:
        notes += tr("\nCALIBRATION_UNAVAILABLE: {0}. Raw recording remains available.", error)
    return notes


def format_sample_time(offset: int, rate: float) -> str:
    """MM:SS.ff uses a sample counter; fractional rates retain explicit seconds.

    Args:
        offset: Position within the input representation.
        rate: Sample or frame rate per second, as declared by this operation.

    Returns:
        Formatted sample time in the selected language.
    """
    if not rate.is_integer():
        return f"{offset / rate:.3f} s"
    whole, frame = divmod(abs(offset), int(rate))
    minutes, seconds = divmod(whole, 60)
    width = max(2, len(str(int(rate) - 1)))
    sign = "-" if offset < 0 else ""
    return f"{sign}{minutes:02}:{seconds:02}.{frame:0{width}}"


@dataclass(frozen=True, slots=True)
class SampleRange:
    """Inclusive local selection; unrelated to source marker slicing semantics.

    Attributes:
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
    """

    first: int
    last: int

    @property
    def count(self) -> int:
        """Return the number of retained samples or items represented by this object.

        Returns:
            The number of retained samples or items represented by this object.
        """
        return self.last - self.first + 1


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
        self.select(index, index)
        if not self.calibrated_enabled or self.analysis is None:
            return None
        context = self.analysis.sample(index).context
        return context.value.replace("_", " ").title() if context is not None else None

    @property
    def localized_notes(self) -> str:
        """Return localized diagnostic text while retaining original diagnostics.

        Returns:
            Localized diagnostic text while retaining original diagnostics.
        """
        if get_language() == "en":
            return self.notes
        lines = [
            f"{item.severity.value.upper()} {item.code} {item.json_path}: "
            f"{diagnostic_message(item.code, item.message)}"
            for item in self.source.diagnostics
        ]
        if self.calibration_error:
            lines.append(f"CALIBRATION_UNAVAILABLE: {tr(self.calibration_error)}")
        return "\n".join(lines) or tr("No import diagnostics.")

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
        return (
            (
                tr("Vertical"),
                tr("Lateral (+ right / − left)"),
                tr("Longitudinal (+ acceleration / − braking)"),
            )
            if self.calibrated_enabled
            else ("x", "y", "z")
        )

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
        window = self.smoothing_window
        if window == 1:
            return tr("1 sample • Smoothing off")
        half_ms = (window // 2) / self.sample_rate * 1000
        return tr("{0} samples • ±{1:g} ms • Centered mean", window, half_ms)

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
            notes=_import_notes(self.source, error),
        ).with_calibration(self.calibrated_enabled)

    @property
    def metadata_fields(self) -> tuple[tuple[str, str], ...]:
        """Return the recording metadata as localized label/value pairs.

        Returns:
            The recording metadata as localized label/value pairs.
        """
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
        """Return formatted recording metadata for the inspector.

        Returns:
            Formatted recording metadata for the inspector.
        """
        return "  |  ".join(f"{tr(label)}: {value}" for label, value in self.metadata_fields)

    @property
    def metadata_rows_text(self) -> str:
        """Return the recording's row, seat and train metadata when available.

        Returns:
            The recording's row, seat and train metadata when available.
        """
        return "\n".join(f"{tr(label)}: {value}" for label, value in self.metadata_fields)

    @property
    def overview_text(self) -> str:
        """Return the compact recording overview used by the workspace header.

        Returns:
            The compact recording overview used by the workspace header.
        """
        recording = self.source.recording
        return tr(
            "{0} · {1:,} samples · {2:g} Hz",
            recording.metadata.device or tr("Unknown device"),
            self.count,
            self.sample_rate,
        )

    @property
    def availability_text(self) -> str:
        """Describe available calibration, gravity, GPS and time information.

        Returns:
            Localized description of available recording capabilities.
        """
        gravity = (
            tr("available") if self.source.recording.motion.gravity is not None else tr("absent")
        )
        return tr(
            "Gravity {0} · GPS {1} · Inferred time",
            gravity,
            tr(self.source.recording.gps_status.value),
        )

    def sample_clock_text(self, index: int) -> str:
        """Format recording and replay clocks for one source sample.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Localized recording and replay clock text.
        """
        self.select(index, index)
        return tr(
            "Replay {0} · Recording {1:.3f} s · {2:g} Hz",
            self.replay_text(index),
            self.time_at(index),
            self.sample_rate,
        )

    def sample_cards(self, index: int) -> tuple[tuple[str, str, str], ...]:
        """Format the three force cards for one source sample.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Three force readouts, each containing its name, formatted value and availability
            hint.
        """
        self.select(index, index)
        values_at_sample = self._sample_values(index)
        cards: list[tuple[str, str, str]] = []
        for axis, name in enumerate(self.channel_names):
            value = values_at_sample[axis]
            if value is None:
                cards.append((name.partition(" (")[0], "—", tr("Unavailable")))
            elif self.calibrated_enabled:
                meanings = (
                    (tr("Vertical force"), tr("Vertical force")),
                    (tr("Left"), tr("Right")),
                    (tr("Braking"), tr("Acceleration")),
                )
                meaning = tr("Neutral") if value == 0 else meanings[axis][int(value > 0)]
                if axis == 0:
                    context = self.vertical_context_label(index)
                    if context is not None:
                        meaning = tr(context)
                cards.append((name.partition(" (")[0], tr("{0:+.2f} g", value), meaning))
            else:
                cards.append((name, tr("{0:.6g}", value), tr("Unit unknown")))
        return tuple(cards)

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
        first, last = self.ride_bounds
        low, high = self.time_at(first), self.time_at(last)
        if low == high:
            low = max(0.0, min(low, self.duration - 1 / self.sample_rate))
            high = min(self.duration, low + 1 / self.sample_rate)
        return low, high

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
        return (
            tr("Replay time (MM:SS.ff @ {0:g} Hz; ff = sample)", self.sample_rate)
            if self.sample_rate.is_integer()
            else tr("Replay time (s @ {0:g} Hz)", self.sample_rate)
        )

    def replay_text(self, index: int) -> str:
        """Format a source sample as start-relative replay time.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Formatted replay time relative to the selected origin.
        """
        self.select(index, index)
        return format_sample_time(index - self.ride_bounds[0], self.sample_rate)

    def time_at(self, index: int) -> float:
        """Convert a source sample index to recording seconds.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            Time from the recording origin in seconds.
        """
        self.select(index, index)
        return index / self.sample_rate

    def sample_at_time(self, seconds: float) -> int:
        """Return the nearest sample, clamped to the recording bounds.

        Args:
            seconds: Time in seconds in the clock or coordinate system used by this operation.

        Returns:
            The nearest sample, clamped to the recording bounds.

        Raises:
            ValueError: Sample time must be finite.
        """
        if not isfinite(seconds):
            raise ValueError("Sample time must be finite")
        return round(min(self.count - 1, max(0.0, seconds * self.sample_rate)))

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
        if type(first) is not int or type(last) is not int or not 0 <= first <= last < self.count:
            raise ValueError("Selection requires bounded, ordered sample indices")
        return SampleRange(first, last)

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
        """Return retained source and processing details for the technical inspector.

        Returns:
            Retained source and processing details for the technical inspector.
        """
        recording = self.source.recording
        rate = recording.motion.sample_rate
        rows = (
            (
                tr("Source format"),
                "RFDB" if recording.source_format is RecordingFormat.RFDB else "Ride Forces",
            ),
            (tr("Schema version"), recording.schema_version or tr("No schema version")),
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

    def _sample_values(self, index: int) -> tuple[float | None, float | None, float | None]:
        if self.analysis is not None:
            sample = self.analysis.sample(index)
            if self.calibrated_enabled:
                force = sample.smoothed
                return (
                    (force.vertical, force.lateral, force.longitudinal)
                    if force
                    else (None, None, None)
                )
            return sample.raw.x, sample.raw.y, sample.raw.z
        raw = self.source.recording.motion.acceleration[index]
        return raw.x, raw.y, raw.z

    def sample_text(self, index: int, *, rich: bool = False) -> str:
        """Format the available values and context for one source sample.

        Args:
            index: Source or collection index selected for this operation.
            rich: Whether to emit supported rich-text formatting instead of plain text.

        Returns:
            Localized values and availability context for the source sample.
        """
        self.select(index, index)
        if rich:
            rows = (
                (tr("Sample"), tr("{0:,}", index)),
                (tr("Replay"), tr("{0} @ {1:g} Hz", self.replay_text(index), self.sample_rate)),
                (tr("Recording"), tr("{0:.3f} s", self.time_at(index))),
                *(
                    (name, tr("{0:.6g}", value) if value is not None else tr("Unavailable"))
                    for name, value in zip(
                        self.channel_names,
                        self._sample_values(index),
                        strict=True,
                    )
                ),
            )
            return _details_table(rows)
        values = "   ".join(
            tr("{0} {1:.6g}", name, value) if value is not None else f"{name} {tr('Unavailable')}"
            for name, value in zip(self.channel_names, self._sample_values(index), strict=True)
        )
        return tr(
            "Sample {0:,}   |   Replay {1} @ {2:g} Hz   |   Recording {3:.3f} s   |   {4}",
            index,
            self.replay_text(index),
            self.sample_rate,
            self.time_at(index),
            values,
        )


def present_recording(
    source: ImportSuccess,
    *,
    analysis: "RecordingAnalysis | None" = None,
) -> ExplorerData:
    """Build explorer presentation data from a successful lossless import.

    Args:
        source: Input recording, retained source representation or source path to read.
        analysis: Prepared recording-analysis snapshot used by this operation.

    Returns:
        Explorer data retaining the original recording and prepared analysis.

    Raises:
        ValueError: Source values exceed the chart display range. Analysis belongs to
            another import.
    """
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
    low = min(0.0, min(min(axis) for axis in channels))
    high = max(0.0, max(max(axis) for axis in channels))
    # Pad each signed extremum independently; keep zero visible for one-sided data.
    value_range = (low * 1.05, high * 1.05) if low < high else (-1.0, 1.0)
    if not all(isfinite(value) for value in value_range):
        raise ValueError("Source values exceed the chart display range")
    calibration_error = None
    if analysis is not None and analysis.source is not source:
        raise ValueError("Analysis belongs to another import")
    if find_spec("numpy") is not None:
        from ride_forces_analyzer.analysis.recording import source_app_configuration
        from ride_forces_analyzer.analysis.service import AnalysisService

        if analysis is None:
            service = AnalysisService()
            service.request_analysis(
                source,
                source_app_configuration(),
                calculation_time=datetime.now(UTC),
            )
            state = service.get_state()
            analysis = state.snapshot
            calibration_error = state.failure.message if state.failure is not None else None
            service.close()
        if analysis is not None:
            reason = analysis.forces.smoothed.availability.reason
            calibration_error = reason.message if reason is not None else None
    else:
        calibration_error = tr("The optional NumPy analysis package is not installed")
    notes = _import_notes(source, calibration_error)
    return ExplorerData(
        source,
        channels,
        title,
        summary,
        notes,
        value_range,
        calibration_error=calibration_error,
        analysis=analysis,
    )


def load_recording(path: Path) -> ExplorerData | ImportFailure:
    """Read an original using M2; keep source ownership and all warnings intact.

    Args:
        path: Filesystem path read or written by this operation.

    Returns:
        Prepared explorer data on success, otherwise a structured import failure.
    """
    source = import_forces(path)
    return source if isinstance(source, ImportFailure) else present_recording(source)


def failure_text(failure: ImportFailure) -> str:
    """Bounded field-oriented feedback, never an exception or recording payload.

    Args:
        failure: Structured failure information.

    Returns:
        Bounded diagnostic text suitable for display.
    """
    items = failure.diagnostics[:5]
    return tr("Could not open recording. ") + "; ".join(
        f"{item.code}: {diagnostic_message(item.code, item.message)}" for item in items
    )
