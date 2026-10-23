"""Chart marker actions persist independently and preserve original source bytes."""

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.ui.helpers import wait_until


SOURCE = Path("tests/fixtures/real/VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces")


def test_chart_context_markers_save_reopen_and_reset_independently(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    original_bytes = SOURCE.read_bytes()
    window.open_path(SOURCE)
    wait_until(lambda: window.data is not None)
    data = window.data
    assert data is not None and data.analysis is not None
    original = data.ride_bounds

    def choose(sample: int, text: str | None, *, enabled: bool = True) -> None:
        window.axis_x.setRange((sample - 100) / data.sample_rate, (sample + 100) / data.sample_rate)
        view = window.chart_view
        point = view.mapFromScene(window.chart.mapToScene(window.chart.plotArea().center()))
        viewport = window.axis_x.min(), window.axis_x.max()
        selected = window.slider.value()

        def pick() -> None:
            menu = QApplication.activePopupWidget()
            assert isinstance(menu, QMenu)
            actions = menu.actions()
            assert [a.text() for a in actions if not a.isSeparator()] == [
                "Set start here",
                "Set end here",
                "Reset start to original",
                "Reset end to original",
                "Reset all ride markers",
            ]
            assert actions[2].isSeparator()
            if text is not None:
                action = next(a for a in actions if a.text() == text)
                assert action.isEnabled() is enabled
                if enabled:
                    action.trigger()
            menu.close()

        QTimer.singleShot(0, pick)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.RightButton, pos=point)
        if text is None or not enabled:
            assert (window.axis_x.min(), window.axis_x.max()) == viewport
            assert window.slider.value() == selected

    def expect(bounds: tuple[int, int]) -> None:
        wait_until(lambda: window.data is not None and window.data.ride_bounds == bounds)

    choose(1700, None)
    choose(1700, "Set start here")
    expect((1700, original[1]))
    choose(9000, "Set end here")
    expect((1700, 9000))
    assert window.preferences.recording_bounds(data.source.source_sha256) == (1700, 9000)
    assert window.data is not None and window.data.replay_text(1700) == "00:00.00"
    choose(1000, "Set end here", enabled=False)
    expect((1700, 9000))
    window.open_path(SOURCE)
    wait_until(lambda: window.data is not None and window.data.source is not data.source)
    expect((1700, 9000))
    assert window.slider.value() == 1700
    choose(5000, "Reset start to original")
    expect((original[0], 9000))
    choose(5000, "Reset end to original")
    expect(original)
    assert window.preferences.recording_bounds(data.source.source_sha256) is None
    choose(1800, "Set start here")
    expect((1800, original[1]))
    choose(9100, "Set end here")
    expect((1800, 9100))
    choose(5000, "Reset all ride markers")
    expect(original)
    assert window.preferences.recording_bounds(data.source.source_sha256) is None
    assert SOURCE.read_bytes() == original_bytes
