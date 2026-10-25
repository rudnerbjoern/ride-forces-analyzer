"""Frame ETA uses measured throughput and handles startup and completion."""

from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress, remaining_seconds


def test_eta_follows_average_frame_cost() -> None:
    assert remaining_seconds(10, 100, 1000) == 90
    assert remaining_seconds(30, 200, 1000) == 120
    assert remaining_seconds(1, 3, 10) == 3
    assert remaining_seconds(100, 1000, 1000) == 0
    assert remaining_seconds(1, 0, 1000) is None


def test_export_progress_owns_estimate_and_does_not_predict_finalization() -> None:
    assert ExportProgress(ExportPhase.PREPARING).remaining_seconds is None
    starting = ExportProgress(ExportPhase.RENDERING, 0, 1000, 5)
    assert starting.percent == 0 and starting.remaining_seconds is None
    measured = ExportProgress(ExportPhase.RENDERING, 100, 1000, 10, True)
    assert measured.percent == 10 and measured.remaining_seconds == 90
    for phase in (ExportPhase.FINALIZING, ExportPhase.COMPLETED):
        update = ExportProgress(phase, 1000, 1000, 100, True)
        assert update.percent == 100 and update.remaining_seconds is None
    # A new video starts its own clock/counters even after a long previous export.
    assert ExportProgress(ExportPhase.RENDERING, 1, 100, 2).remaining_seconds == 198
