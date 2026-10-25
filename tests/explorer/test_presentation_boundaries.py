"""Presentation fallbacks and context ranges without desktop windows."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.analysis.recording import AnalysisState, RequestStatus, VerticalContext
from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.explorer import present_recording
from ride_forces_analyzer.explorer.text import failure_text
from ride_forces_analyzer.i18n import Language, get_language, set_language
from ride_forces_analyzer.importers import ImportFailure, import_forces_bytes
from tests.exports.test_csv_export import snapshot


def test_unprepared_view_retains_raw_values_and_default_recipe() -> None:
    analysis = snapshot()
    view = present_recording(analysis.source, analysis=analysis).with_calibration(True)
    raw = replace(view, analysis=None)
    assert raw.smoothing_window == 11 and raw.with_smoothing(3) is raw
    assert raw.vertical_context_segments == ()
    assert raw.vertical_context_label(0) is None
    assert raw.ride_bounds == (2, 5)
    assert "Sample 0" in raw.sample_text(0)
    assert "0.000" in raw.sample_clock_text(0)
    assert "GPS absent" in raw.availability_text
    assert "6 samples" in raw.overview_text
    assert "ff = sample" in raw.replay_time_label
    fractional = snapshot(rate=59.94)
    assert (
        "s @ 59.94 Hz"
        in present_recording(
            fractional.source,
            analysis=fractional,
        ).replay_time_label
    )
    assert len(view.with_calibration(False).value_ticks) == 5
    with pytest.raises(ValueError, match="another import"):
        replace(view, source=snapshot().source)
    wide = replace(view, value_range=(-30, 30))
    assert wide.value_ticks == (-30.0, -15.0, -1.0, 0.0, 1.0, 15.0, 30.0)
    assert "Smoothing off" in view.with_smoothing(1).smoothing_text
    assert "Centered mean" in view.smoothing_text
    single = view.with_analysis(
        replace(
            analysis,
            configuration=replace(
                analysis.configuration,
                ride_bounds=(5, 5),
            ),
        ),
    )
    assert single.default_time_range == (4 / single.sample_rate, 5 / single.sample_rate)


def test_context_segments_share_boundaries_and_empty_context_has_no_labels() -> None:
    analysis = snapshot()
    normal, airtime = VerticalContext.NORMAL_GS, VerticalContext.AIRTIME
    labels = (normal, normal, airtime, airtime, normal, normal)
    analysis = replace(analysis, context=replace(analysis.context, labels=labels))
    view = present_recording(analysis.source, analysis=analysis).with_calibration(True)
    assert view.vertical_context_segments == (
        ("Normal Gs", 0, 2),
        ("Airtime", 2, 4),
        ("Normal Gs", 4, 5),
    )
    assert view.with_calibration(False).vertical_context_segments == ()
    for missing in (None, ()):
        # Test the presentation guard with an owned incomplete stage, without adoption.
        empty = replace(analysis, context=replace(analysis.context, labels=missing))
        current = replace(view, analysis=empty)
        assert current.vertical_context_segments == ()
        if missing is None:
            assert current.vertical_context_label(0) is None
            assert current.sample_cards(0)[0][2] == "Vertical force"


def test_loading_without_snapshot_retains_raw_view_and_localized_failure_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = snapshot(calibrated=False).source
    service = Mock()
    service.get_state.return_value = AnalysisState(None, None, None, 0, RequestStatus.IDLE)
    monkeypatch.setattr("ride_forces_analyzer.analysis.service.AnalysisService", lambda: service)
    data = present_recording(source)
    assert data.analysis is None and not data.calibration_available
    service.close.assert_called_once()
    previous = get_language()
    try:
        set_language(Language.GERMAN)
        assert data.localized_notes
        failed = replace(data, calibration_error="Analysis unavailable")
        assert "CALIBRATION_UNAVAILABLE" in failed.localized_notes
    finally:
        set_language(previous)
    failure = import_forces_bytes(b"{")
    assert isinstance(failure, ImportFailure)
    assert failure.diagnostics[0].code in failure_text(failure)


def test_loading_rejects_padding_that_would_overflow_the_chart_range() -> None:
    source = snapshot().source
    motion = replace(source.recording.motion, acceleration=(Vector3(1.79e308, 0, 0),) * 6)
    source = replace(source, recording=replace(source.recording, motion=motion))
    with pytest.raises(ValueError, match="exceed the chart display range"):
        present_recording(source)
