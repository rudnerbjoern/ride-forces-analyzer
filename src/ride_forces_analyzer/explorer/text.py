"""Explorer metadata, diagnostic and sample text without Qt widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words cellspacing

from __future__ import annotations

from ride_forces_analyzer.i18n import Language, diagnostic_message, get_language, tr
from html import escape
from typing import TYPE_CHECKING
from ride_forces_analyzer.formatting.time import format_sample_time
from ride_forces_analyzer.domain import RecordingFormat, SourceNumber
from ride_forces_analyzer.importers import ImportFailure, ImportSuccess

if TYPE_CHECKING:
    from .model import ExplorerData


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


def import_notes(source: ImportSuccess, error: str | None) -> str:
    """Format retained import diagnostics and an optional calibration failure.

    Args:
        source: Original import with its diagnostic messages and source paths.
        error: Calibration failure text, or None when no failure is present.

    Returns:
        Import diagnostic text without changing the original diagnostic objects.
    """
    notes = "\n".join(
        f"{item.severity.value.upper()} {item.code} {item.json_path}: {item.message}"
        for item in source.diagnostics
    ) or tr("No import diagnostics.")
    if error:
        notes += tr("\nCALIBRATION_UNAVAILABLE: {0}. Raw recording remains available.", error)
    return notes


def vertical_context_label(data: ExplorerData, index: int) -> str | None:
    """Format the prepared sample category without classifying forces again.

    Args:
        data: Bound explorer presentation data.
        index: Source or collection index selected for this operation.

    Returns:
        Localized context label, or None when classification is unavailable.
    """
    data.select(index, index)
    if not data.calibrated_enabled or data.analysis is None:
        return None
    context = data.analysis.sample(index).context
    return context.value.replace("_", " ").title() if context is not None else None


def localized_notes(data: ExplorerData) -> str:
    """Return localized diagnostic text while retaining original diagnostics.

    Args:
        data: Bound explorer presentation data.

    Returns:
        Localized diagnostic text while retaining original diagnostics.
    """
    if get_language() is Language.ENGLISH:
        return data.notes
    lines = [
        f"{item.severity.value.upper()} {item.code} {item.json_path}: "
        f"{diagnostic_message(item.code, item.message)}"
        for item in data.source.diagnostics
    ]
    if data.calibration_error:
        lines.append(f"CALIBRATION_UNAVAILABLE: {tr(data.calibration_error)}")
    return "\n".join(lines) or tr("No import diagnostics.")


def channel_names(data: ExplorerData) -> tuple[str, str, str]:
    """Return the display names of the currently plotted channels.

    Args:
        data: Bound explorer presentation data.

    Returns:
        The display names of the currently plotted channels.
    """
    return (
        (
            tr("Vertical"),
            tr("Lateral (+ right / − left)"),
            tr("Longitudinal (+ acceleration / − braking)"),
        )
        if data.calibrated_enabled
        else ("x", "y", "z")
    )


def smoothing_text(data: ExplorerData) -> str:
    """Return the localized description of the current smoothing window.

    Args:
        data: Bound explorer presentation data.

    Returns:
        The localized description of the current smoothing window.
    """
    window = data.smoothing_window
    if window == 1:
        return tr("1 sample • Smoothing off")
    half_ms = (window // 2) / data.sample_rate * 1000
    return tr("{0} samples • ±{1:g} ms • Centered mean", window, half_ms)


def metadata_fields(data: ExplorerData) -> tuple[tuple[str, str], ...]:
    """Return the recording metadata as localized label/value pairs.

    Args:
        data: Bound explorer presentation data.

    Returns:
        The recording metadata as localized label/value pairs.
    """
    recording = data.source.recording
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


def metadata_text(data: ExplorerData) -> str:
    """Return formatted recording metadata for the inspector.

    Args:
        data: Bound explorer presentation data.

    Returns:
        Formatted recording metadata for the inspector.
    """
    return "  |  ".join(f"{tr(label)}: {value}" for label, value in data.metadata_fields)


def metadata_rows_text(data: ExplorerData) -> str:
    """Return the recording's row, seat and train metadata when available.

    Args:
        data: Bound explorer presentation data.

    Returns:
        The recording's row, seat and train metadata when available.
    """
    return "\n".join(f"{tr(label)}: {value}" for label, value in data.metadata_fields)


def overview_text(data: ExplorerData) -> str:
    """Return the compact recording overview used by the workspace header.

    Args:
        data: Bound explorer presentation data.

    Returns:
        The compact recording overview used by the workspace header.
    """
    recording = data.source.recording
    return tr(
        "{0} · {1:,} samples · {2:g} Hz",
        recording.metadata.device or tr("Unknown device"),
        data.count,
        data.sample_rate,
    )


def availability_text(data: ExplorerData) -> str:
    """Describe available calibration, gravity, GPS and time information.

    Args:
        data: Bound explorer presentation data.

    Returns:
        Localized description of available recording capabilities.
    """
    gravity = tr("available") if data.source.recording.motion.gravity is not None else tr("absent")
    return tr(
        "Gravity {0} · GPS {1} · Inferred time",
        gravity,
        tr(data.source.recording.gps_status.value),
    )


def sample_clock_text(data: ExplorerData, index: int) -> str:
    """Format recording and replay clocks for one source sample.

    Args:
        data: Bound explorer presentation data.
        index: Source or collection index selected for this operation.

    Returns:
        Localized recording and replay clock text.
    """
    data.select(index, index)
    return tr(
        "Replay {0} · Recording {1:.3f} s · {2:g} Hz",
        data.replay_text(index),
        data.time_at(index),
        data.sample_rate,
    )


def sample_cards(data: ExplorerData, index: int) -> tuple[tuple[str, str, str], ...]:
    """Format the three force cards for one source sample.

    Args:
        data: Bound explorer presentation data.
        index: Source or collection index selected for this operation.

    Returns:
        Three force readouts, each containing its name, formatted value and availability
        hint.
    """
    data.select(index, index)
    values_at_sample = _sample_values(data, index)
    cards: list[tuple[str, str, str]] = []
    for axis, name in enumerate(data.channel_names):
        value = values_at_sample[axis]
        if value is None:
            cards.append((name.partition(" (")[0], "—", tr("Unavailable")))
        elif data.calibrated_enabled:
            meanings = (
                (tr("Vertical force"), tr("Vertical force")),
                (tr("Left"), tr("Right")),
                (tr("Braking"), tr("Acceleration")),
            )
            meaning = tr("Neutral") if value == 0 else meanings[axis][int(value > 0)]
            if axis == 0:
                context = data.vertical_context_label(index)
                if context is not None:
                    meaning = tr(context)
            cards.append((name.partition(" (")[0], tr("{0:+.2f} g", value), meaning))
        else:
            cards.append((name, tr("{0:.6g}", value), tr("Unit unknown")))
    return tuple(cards)


def extrema_text(
    data: ExplorerData,
    first: int,
    last: int,
    *,
    rich: bool = False,
) -> tuple[str, tuple[str, ...]]:
    """Format the selected interval's extrema and calculation context.

    Args:
        data: Bound explorer presentation data.
        first: First included source sample index.
        last: Last included source sample index.
        rich: Whether to emit supported rich-text formatting instead of plain text.

    Returns:
        Selection description and formatted per-channel extrema.
    """
    result = data.selection_extrema(first, last)
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
                tr("{0:+.2f} g", point.value) if result.unit == "g" else tr("{0:.6g}", point.value)
            )
            points.append(
                tr(
                    "{0} {1} · Replay {2}\nSample {3} · Recording {4:.3f} s",
                    label,
                    value,
                    data.replay_text(point.index),
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
                f'<td align="right">{escape(data.replay_text(point.index))}</td></tr>'
                f'<tr><td colspan="3"><small>{escape(details)}</small></td></tr>',
            )
        rows.append(
            '<table width="100%" cellspacing="0" cellpadding="2">'
            f'<tr><th colspan="2" align="left">{escape(tr(channel.name))}</th>'
            f'<td align="right">{escape(tr("Replay"))}</td></tr>' + "".join(table_rows) + "</table>"
            if rich
            else f"{tr(channel.name)}\n" + "\n".join(points),
        )
    return tr(
        "{0} · {1:g} Hz · {2:,} selected",
        context,
        result.sample_rate,
        result.count,
    ), tuple(rows)


def replay_time_label(data: ExplorerData) -> str:
    """Return the localized label for the recording's replay time notation.

    Args:
        data: Bound explorer presentation data.

    Returns:
        The localized label for the recording's replay time notation.
    """
    return (
        tr("Replay time (MM:SS.ff @ {0:g} Hz; ff = sample)", data.sample_rate)
        if data.sample_rate.is_integer()
        else tr("Replay time (s @ {0:g} Hz)", data.sample_rate)
    )


def replay_text(data: ExplorerData, index: int) -> str:
    """Format a source sample as start-relative replay time.

    Args:
        data: Bound explorer presentation data.
        index: Source or collection index selected for this operation.

    Returns:
        Formatted replay time relative to the selected origin.
    """
    data.select(index, index)
    return format_sample_time(index - data.ride_bounds[0], data.sample_rate)


def technical_summary(data: ExplorerData) -> str:
    """Return retained source and processing details for the technical inspector.

    Args:
        data: Bound explorer presentation data.

    Returns:
        Retained source and processing details for the technical inspector.
    """
    recording = data.source.recording
    rate = recording.motion.sample_rate
    rows = (
        (
            tr("Source format"),
            "RFDB" if recording.source_format is RecordingFormat.RFDB else "Ride Forces",
        ),
        (tr("Schema version"), recording.schema_version or tr("No schema version")),
        (tr("Device"), recording.metadata.device or tr("Unknown device")),
        (tr("Samples"), tr("{0:,}", data.count)),
        (tr("Sample rate"), tr("{0:g} Hz ({1})", rate.value, rate.origin.value)),
        (tr("Time basis"), "INFERRED_UNIFORM"),
        (
            tr("Gravity"),
            tr("available") if recording.motion.gravity is not None else tr("absent"),
        ),
        ("GPS", tr(recording.gps_status.value)),
    )
    return _details_table(rows)


def _sample_values(
    data: ExplorerData,
    index: int,
) -> tuple[float | None, float | None, float | None]:
    """Read existing prepared or raw sample values without recalculation."""
    if data.analysis is not None:
        sample = data.analysis.sample(index)
        if data.calibrated_enabled:
            force = sample.smoothed
            return (
                (force.vertical, force.lateral, force.longitudinal) if force else (None, None, None)
            )
        return sample.raw.x, sample.raw.y, sample.raw.z
    raw = data.source.recording.motion.acceleration[index]
    return raw.x, raw.y, raw.z


def sample_text(data: ExplorerData, index: int, *, rich: bool = False) -> str:
    """Format the available values and context for one source sample.

    Args:
        data: Bound explorer presentation data.
        index: Source or collection index selected for this operation.
        rich: Whether to emit supported rich-text formatting instead of plain text.

    Returns:
        Localized values and availability context for the source sample.
    """
    data.select(index, index)
    if rich:
        rows = (
            (tr("Sample"), tr("{0:,}", index)),
            (tr("Replay"), tr("{0} @ {1:g} Hz", data.replay_text(index), data.sample_rate)),
            (tr("Recording"), tr("{0:.3f} s", data.time_at(index))),
            *(
                (name, tr("{0:.6g}", value) if value is not None else tr("Unavailable"))
                for name, value in zip(
                    data.channel_names,
                    _sample_values(data, index),
                    strict=True,
                )
            ),
        )
        return _details_table(rows)
    values = "   ".join(
        tr("{0} {1:.6g}", name, value) if value is not None else f"{name} {tr('Unavailable')}"
        for name, value in zip(data.channel_names, _sample_values(data, index), strict=True)
    )
    return tr(
        "Sample {0:,}   |   Replay {1} @ {2:g} Hz   |   Recording {3:.3f} s   |   {4}",
        index,
        data.replay_text(index),
        data.sample_rate,
        data.time_at(index),
        values,
    )


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
