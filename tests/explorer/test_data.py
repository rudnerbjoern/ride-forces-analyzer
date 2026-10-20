"""Pure raw-source presentation and local inclusive selection contracts."""

from dataclasses import replace

import json

import pytest

from ride_forces_analyzer.domain import (
    Attribute,
    MotionSequence,
    Recording,
    RecordingMetadata,
    SampleRate,
    SourceNumber,
    ValueOrigin,
    Vector3,
)
from ride_forces_analyzer.explorer import format_sample_time, present_recording
from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes


def test_nearest_sample_uses_recording_time_and_clamps_bounds(
    synthetic_recording: Recording,
) -> None:
    view = present_recording(ImportSuccess(synthetic_recording))
    for seconds, expected in (
        (-1.0, 0),
        (0.0, 0),
        (0.49 / view.sample_rate, 0),
        (0.51 / view.sample_rate, 1),
        (view.duration, view.count - 1),
        (view.duration + 1, view.count - 1),
    ):
        assert view.sample_at_time(seconds) == expected
    for invalid in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="finite"):
            view.sample_at_time(invalid)


def test_technical_tables_preserve_provenance_precision_and_literal_metadata(
    synthetic_recording: Recording,
) -> None:
    recording = replace(
        synthetic_recording,
        metadata=replace(synthetic_recording.metadata, device="<b>Phone & Watch</b>"),
    )
    view = present_recording(ImportSuccess(recording))
    summary = view.technical_summary
    assert "&lt;b&gt;Phone &amp; Watch&lt;/b&gt;" in summary
    assert "<b>Phone" not in summary
    for value in ("INFERRED_UNIFORM", "default", "Gravity", "GPS", "absent"):
        assert value in summary
    rich = view.sample_text(1, rich=True)
    assert rich.count("<tr>") == 6
    for text in ("Sample", "Replay", "Recording", view.replay_text(1), f"{view.time_at(1):.3f} s"):
        assert text in rich
    for name, channel in zip(view.channel_names, view.plotted_channels, strict=True):
        assert name in rich and f"{channel[1]:.6g}" in rich
    assert "<table" not in view.sample_text(1)


def test_raw_view_preserves_original_and_exact_source_axes(synthetic_recording: Recording) -> None:
    source = ImportSuccess(synthetic_recording)
    view = present_recording(source)
    assert (
        view.source is source
        and view.source.recording.source.original_bytes == synthetic_recording.source.original_bytes
    )
    assert view.channels == ((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
    assert view.markers == (("startIndex", 0), ("endIndex", 1))
    assert view.count == 2
    assert view.value_range == (0.0, 1.05)
    assert view.select_visible(-10, 100).count == 2
    assert view.select_visible(0.2 / view.sample_rate, 0.8 / view.sample_rate).count == 2
    assert view.select(0, 1).count == 2
    assert view.select(1, 1).count == 1
    assert "Sample 1" in view.sample_text(1)
    assert "Gravity absent" in view.summary and "GPS absent" in view.summary
    assert "default" in view.summary


@pytest.mark.parametrize("first,last", [(-1, 0), (0, 2), (1, 0), (True, 1)])
def test_local_selection_rejects_invalid_ranges(
    synthetic_recording: Recording,
    first: int,
    last: int,
) -> None:
    view = present_recording(ImportSuccess(synthetic_recording))
    with pytest.raises(ValueError):
        view.select(first, last)
    with pytest.raises(ValueError):
        view.sample_text(-1)


def test_inferred_seconds_and_viewport_boundaries(synthetic_recording: Recording) -> None:
    view = present_recording(ImportSuccess(synthetic_recording))
    assert view.sample_rate == 50
    assert view.time_at(0) == 0
    assert view.time_at(1) == 0.02
    assert view.duration == 0.02
    assert "0.020 s" in view.sample_text(1)
    assert "INFERRED_UNIFORM" in view.summary and "default" in view.summary
    assert view.select_visible(0.02, 0.02) == view.select(1, 1)
    for low, high in ((float("nan"), 1), (0, float("inf")), (1, 0)):
        with pytest.raises(ValueError):
            view.select_visible(low, high)


@pytest.mark.parametrize("rate", [25.0, 50.0, 100.0])
def test_source_rate_and_exact_sample_round_trip(
    synthetic_recording: Recording,
    rate: float,
) -> None:
    recording = replace(
        synthetic_recording,
        motion=MotionSequence(
            [Vector3(0, 0, 1)] * 100,
            sample_rate=SampleRate(rate, ValueOrigin.SOURCE),
        ),
    )
    view = present_recording(ImportSuccess(recording))
    assert view.duration == 99 / rate
    assert "source" in view.summary
    for index in range(view.count):
        assert view.select_visible(view.time_at(index), view.time_at(index)) == view.select(
            index,
            index,
        )


@pytest.mark.parametrize(
    "values,expected",
    [
        ((-2.0, 5.0, 1.0), (-2.1, 5.25)),
        ((1.0, 2.0, 3.0), (0.0, 3.15)),
        ((-1.0, -2.0, -3.0), (-3.15, 0.0)),
        ((0.0, 0.0, 0.0), (-1.0, 1.0)),
    ],
)
def test_fixed_value_range_pads_signed_extrema(
    synthetic_recording: Recording,
    values: tuple[float, float, float],
    expected: tuple[float, float],
) -> None:
    recording = replace(synthetic_recording, motion=MotionSequence([Vector3(*values)] * 2))
    view = present_recording(ImportSuccess(recording))
    assert view.value_range == pytest.approx(expected)


@pytest.mark.parametrize("start,end", [(1, 2), (None, 2), (1, None), (None, None)])
def test_default_zoom_and_missing_source_boundaries(start: int | None, end: int | None) -> None:
    root: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "sampleRate": 25,
        "accelerationSequence": [{"x": 0, "y": 1, "z": 0}] * 4,
    }
    if start is not None:
        root["startIndex"] = start
    if end is not None:
        root["endIndex"] = end
    raw = json.dumps(root).encode()
    source = import_forces_bytes(raw)
    assert isinstance(source, ImportSuccess)
    view = present_recording(source)
    assert view.default_time_range == (
        (start if start is not None else 0) / 25,
        (end if end is not None else 3) / 25,
    )
    assert dict(view.markers) == {
        key: value for key, value in (("startIndex", start), ("endIndex", end)) if value is not None
    }
    assert source.recording.source.original_bytes == raw
    assert sum(item.code == "INDEX_DEFAULTED" for item in source.diagnostics) == (start is None) + (
        end is None
    )


def test_available_ride_metadata_without_invented_values(synthetic_recording: Recording) -> None:
    assert present_recording(ImportSuccess(synthetic_recording)).metadata_text == ""
    recording = replace(
        synthetic_recording,
        metadata=RecordingMetadata(name="Ride <A>", location="Park B"),
        attributes=(
            Attribute("1", "Train", "Blue"),
            Attribute("2", "Row", SourceNumber("0")),
            Attribute("3", "Seat", "2"),
            Attribute("4", "Row", "3"),
            Attribute("5", "Seat", None),
            Attribute("6", "Unrelated", "ignored"),
        ),
    )
    view = present_recording(ImportSuccess(recording))
    assert (
        view.metadata_text
        == "Ride: Ride <A>  |  Park: Park B  |  Train: Blue  |  Row: 0  |  Row: 3  |  Seat: 2"
    )
    assert view.source.recording.attributes == recording.attributes


def test_raw_explorer_import_does_not_require_optional_numpy() -> None:
    import subprocess
    import sys

    script = """
import sys
from pathlib import Path
import ride_forces_analyzer.explorer as explorer
from ride_forces_analyzer.importers import ImportSuccess, import_forces
assert 'numpy' not in sys.modules
explorer.find_spec = lambda name: None
source = import_forces(next(Path('tests/fixtures/real').glob('Manta-*.forces')))
assert isinstance(source, ImportSuccess)
view = explorer.present_recording(source)
assert view.reference is None and len(view.channels[0]) == 9640
assert view.selection_extrema(0, 100).count == 101
assert 'numpy' not in sys.modules
print('Raw explorer remains independent of optional NumPy')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
    assert b"Raw explorer remains independent" in result.stdout


@pytest.mark.parametrize(
    "offset,rate,expected",
    [
        (0, 50.0, "00:00.00"),
        (49, 50.0, "00:00.49"),
        (50, 50.0, "00:01.00"),
        (4597, 50.0, "01:31.47"),
        (-47, 50.0, "-00:00.47"),
        (24, 25.0, "00:00.24"),
        (99, 100.0, "00:00.99"),
        (1, 29.97, "0.033 s"),
    ],
)
def test_replay_sample_counter_format(offset: int, rate: float, expected: str) -> None:
    assert format_sample_time(offset, rate) == expected


@pytest.mark.parametrize("defect", ["none", "missing", "parallel", "malformed"])
def test_calibration_for_new_recordings_and_safe_raw_fallback(defect: str) -> None:
    root: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "name": "Previously unseen ride",
        "accelerationSequence": [{"x": 2, "y": 3, "z": 4}] * 2,
        "verticalDirectionVector": {"x": 0, "y": 1, "z": 0},
        "lateralDirectionVector": {"x": 0, "y": 0, "z": 1},
        "longitudinalDirectionVector": {"x": 1, "y": 0, "z": 0},
    }
    if defect == "missing":
        del root["verticalDirectionVector"]
    elif defect == "parallel":
        root["lateralDirectionVector"] = root["verticalDirectionVector"]
    elif defect == "malformed":
        root["verticalDirectionVector"] = {"x": "invalid", "y": 0, "z": 0}
    raw = json.dumps(root).encode()
    source = import_forces_bytes(raw)
    assert isinstance(source, ImportSuccess)
    data = present_recording(source)
    assert source.recording.source.original_bytes == raw
    if defect == "none":
        assert data.reference is not None and data.reference_error is None
        assert tuple(tuple(axis) for axis in data.with_reference(True).plotted_channels) == (
            (3.0, 3.0),
            (4.0, 4.0),
            (2.0, 2.0),
        )
    else:
        assert data.reference is None and data.reference_error
        assert "CALIBRATION_UNAVAILABLE" in data.notes
        assert data.channels == ((2.0, 2.0), (3.0, 3.0), (4.0, 4.0))


def test_calibrated_axis_includes_reference_levels(synthetic_recording: Recording) -> None:
    from ride_forces_analyzer.analysis.reference import reconstruct_app_reference
    from datetime import UTC, datetime
    from ride_forces_analyzer.domain import RecordingVectors

    recording = replace(
        synthetic_recording,
        motion=MotionSequence([Vector3(0, 0, 0)] * 2),
        vectors=RecordingVectors(
            vertical_direction=Vector3(1, 0, 0),
            lateral_direction=Vector3(0, 1, 0),
            longitudinal_direction=Vector3(0, 0, 1),
        ),
    )
    source = ImportSuccess(recording)
    reference = reconstruct_app_reference(source, calculation_time=datetime.now(UTC))
    view = replace(present_recording(source), reference=reference).with_reference(True)
    assert view.value_range == (-1.05, 1.05)
    assert view.value_ticks == (-1, 0, 1)
    assert view.with_reference(False).value_range == (-1, 1)


def test_focus_metadata_rows_and_sample_cards(synthetic_recording: Recording) -> None:
    view = present_recording(ImportSuccess(synthetic_recording))
    assert view.metadata_rows_text == "\n".join(
        f"{label}: {value}" for label, value in view.metadata_fields
    )
    assert [card[0] for card in view.sample_cards(0)] == ["x", "y", "z"]
    assert all("unknown" in card[2] for card in view.sample_cards(0))
    assert "Recording 0.000 s" in view.sample_clock_text(0)
    with pytest.raises(ValueError):
        view.sample_cards(-1)


@pytest.mark.parametrize(
    ("lateral", "longitudinal", "meanings"),
    [
        (0.4, 0.6, ("Right", "Acceleration")),
        (-0.4, -0.6, ("Left", "Braking")),
        (0.0, 0.0, ("Neutral", "Neutral")),
    ],
)
def test_current_value_card_direction_signs(
    synthetic_recording: Recording,
    lateral: float,
    longitudinal: float,
    meanings: tuple[str, str],
) -> None:
    from ride_forces_analyzer.domain import RecordingVectors

    recording = replace(
        synthetic_recording,
        motion=MotionSequence([Vector3(1, lateral, longitudinal)] * 2),
        vectors=RecordingVectors(
            vertical_direction=Vector3(1, 0, 0),
            lateral_direction=Vector3(0, 1, 0),
            longitudinal_direction=Vector3(0, 0, 1),
        ),
    )
    view = present_recording(ImportSuccess(recording)).with_reference(True)
    cards = view.sample_cards(0)
    assert (cards[1][2], cards[2][2]) == meanings
    assert (cards[1][1], cards[2][1]) == (f"{lateral:+.2f} g", f"{longitudinal:+.2f} g")


def test_vertical_card_uses_shared_stabilized_context(synthetic_recording: Recording) -> None:
    from ride_forces_analyzer.domain import RecordingVectors
    from ride_forces_analyzer.i18n import tr

    recording = replace(
        synthetic_recording,
        motion=MotionSequence([Vector3(value, 0, 0) for value in [1.0] * 50 + [-0.8] * 50]),
        vectors=RecordingVectors(
            vertical_direction=Vector3(1, 0, 0),
            lateral_direction=Vector3(0, 1, 0),
            longitudinal_direction=Vector3(0, 0, 1),
        ),
    )
    view = present_recording(ImportSuccess(recording)).with_reference(True).with_smoothing(1)
    context = view.airtime_context
    assert context is not None
    for index in (99, 50, 49, 75):
        assert view.sample_cards(index)[0][2] == tr(context.at(index))
    assert view.with_reference(False).sample_cards(99)[0][2] == tr("Unit unknown")
    smoothed = view.with_smoothing(11)
    assert smoothed.airtime_context is not None and smoothed.airtime_context is not context


def test_snapshot_presentation_uses_shared_buffers_and_does_not_repeat_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import numpy as np
    from unittest.mock import Mock
    from ride_forces_analyzer.analysis import recording, airtime
    from tests.analysis.test_recording_preparation import synthetic_source

    project = Mock(wraps=recording.project_directions)
    mean = Mock(wraps=recording.centered_mean)
    context = Mock(wraps=airtime.AirtimeContext.prepare)
    monkeypatch.setattr(recording, "project_directions", project)
    monkeypatch.setattr(recording, "centered_mean", mean)
    monkeypatch.setattr(airtime.AirtimeContext, "prepare", context)
    view = present_recording(synthetic_source()).with_reference(True)
    assert view.analysis is not None and view.analysis.forces.smoothed.channels is not None
    channels = view.analysis.forces.smoothed.channels
    assert np.shares_memory(np.asarray(view.plotted_channels[0]), channels[0].values)
    with pytest.raises(ValueError):
        np.asarray(view.plotted_channels[0]).setflags(write=True)
    for active in (False, True, False, True):
        switched = view.with_reference(active)
        assert switched.analysis is view.analysis
        switched.sample_cards(2)
        switched.sample_text(2, rich=True)
        switched.sample_text(2)
        switched.select_visible(0.0, switched.duration)
        switched.selection_extrema(0, 6)
    assert project.call_count == 1 and mean.call_count == 3 and context.call_count == 1
    changed = view.with_smoothing(5)
    assert changed.analysis is not None
    assert changed.analysis.forces.projected is view.analysis.forces.projected
    assert changed.reference is not None and view.reference is not None
    assert all(
        new is old
        for new, old in zip(
            changed.reference.raw_projection,
            view.reference.raw_projection,
            strict=True,
        )
    )
    assert not any("Centered 11-sample" in item for item in changed.reference.confirmed_contracts)
    assert project.call_count == 1 and mean.call_count == 6 and context.call_count == 2


def test_snapshot_replacement_checks_source_and_refreshes_raw_fallback_notes() -> None:
    from ride_forces_analyzer.analysis.models import AnalysisProfile
    from tests.analysis.test_recording_preparation import synthetic_source

    view = present_recording(synthetic_source()).with_reference(True)
    assert view.analysis is not None
    provenance = view.analysis.forces.projected.provenance
    assert provenance is not None
    raw = view.analysis.with_configuration(
        replace(view.analysis.configuration, profile=AnalysisProfile()),
        revision=2,
        calculation_time=provenance.calculation_time,
    )
    fallback = view.with_analysis(raw)
    assert fallback.reference is None and not fallback.reference_enabled
    assert "CALIBRATION_UNAVAILABLE" in fallback.notes
    recovered = fallback.with_analysis(
        raw.with_configuration(
            view.analysis.configuration,
            revision=3,
            calculation_time=provenance.calculation_time,
        ),
    )
    assert "CALIBRATION_UNAVAILABLE" not in recovered.notes
    other = present_recording(synthetic_source(sampleRate=50))
    assert other.analysis is not None
    with pytest.raises(ValueError, match="another import"):
        view.with_analysis(other.analysis)
    with pytest.raises(ValueError, match="another import"):
        present_recording(view.source, analysis=other.analysis)
