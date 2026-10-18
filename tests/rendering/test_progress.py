"""Frame ETA uses measured throughput and handles startup and completion."""

from ride_forces_analyzer.rendering.progress import remaining_seconds


def test_eta_follows_average_frame_cost() -> None:
    assert remaining_seconds(10, 100, 1000) == 90
    assert remaining_seconds(30, 200, 1000) == 120
    assert remaining_seconds(1, 3, 10) == 3
    assert remaining_seconds(100, 1000, 1000) == 0
    assert remaining_seconds(1, 0, 1000) is None
