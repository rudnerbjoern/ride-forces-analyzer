"""Combined is an independent Explorer curve, reusing prepared analysis."""

# cspell:words Kombinierte Kräfte combinées

from dataclasses import replace

import numpy as np

from ride_forces_analyzer.analysis import SampleValues
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import resize_workspace, wait_until


def test_combined_curve_visibility_modes_smoothing_and_missing_samples(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert not window.combined_toggle.isEnabled()
    assert not window.combined_toggle.isVisible()
    assert not window.combined_toggle.isChecked()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None and data.analysis is not None
    assert window.combined_toggle.isEnabled()
    assert window.combined_toggle.isVisible()
    assert not window.combined_toggle.isChecked()
    assert not window.plot.combined_series
    original_range = data.value_range
    window.navigation.position.setValue(100)
    window.plot.axis_x.setRange(data.time_at(50), data.time_at(150))
    state = (
        window.plot.axis_x.min(),
        window.plot.axis_x.max(),
        window.navigation.position.value(),
        window.inspector.first.value(),
        window.inspector.last.value(),
    )
    window.combined_toggle.click()
    current = window.data
    assert current is not None and current.analysis is data.analysis
    assert len(window.plot.combined_series) == 1
    curve = window.plot.combined_series[0]
    assert curve.isVisible() and curve.count() == data.count
    assert current.combined_channel is not None
    assert tuple(point.y() for point in curve.points()) == tuple(current.combined_channel)
    assert window.plot.axis_y.max() >= max(current.combined_channel)
    assert (
        window.plot.axis_x.min(),
        window.plot.axis_x.max(),
        window.navigation.position.value(),
        window.inspector.first.value(),
        window.inspector.last.value(),
    ) == state
    for toggle in window.visibility:
        toggle.setChecked(False)
    assert curve.isVisible()
    window.combined_toggle.click()
    assert not window.plot.combined_series
    assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == original_range
    assert all(not line.isVisible() for line in window.plot.series)
    window.combined_toggle.click()
    window.reference_toggle.setChecked(False)
    assert not window.combined_toggle.isEnabled()
    assert not window.combined_toggle.isVisible()
    assert window.combined_toggle.isChecked()
    assert not window.plot.combined_series
    window.reference_toggle.setChecked(True)
    assert window.combined_toggle.isEnabled()
    assert window.combined_toggle.isVisible()
    assert window.plot.combined_series[0].isVisible()
    window.set_smoothing(0)
    wait_until(lambda: window.data is not None and window.data.smoothing_window == 1)
    current = window.data
    assert current is not None and current.analysis is not None
    assert current.combined_enabled and current.combined_channel is not None
    assert tuple(point.y() for point in window.plot.combined_series[0].points()) == tuple(
        current.combined_channel,
    )
    for toggle in window.visibility:
        toggle.setChecked(True)
    for language, label in (
        (0, "Combined Forces"),
        (1, "Kombinierte Kräfte"),
        (2, "Forces combinées"),
    ):
        window.set_ui_language(language)
        assert window.combined_toggle.text() == label
        assert window.combined_toggle.isChecked()
    window.set_ui_language(0)
    window.reset_button.click()
    for appearance in (0, 1):
        window.set_appearance(appearance)
        resize_workspace(window, 1280, 720)
        assert window.width() == 1280
        assert (
            window.combined_toggle.visibleRegion().boundingRect() == window.combined_toggle.rect()
        )
        assert window.plot.combined_series[0].pen().color().name() == (
            window.theme.chart_combined_force_color
        )
        assert window.theme.combined_force_color in window.combined_toggle.styleSheet()
        assert window.grab().save(f".tmp/explorer-combined-{appearance}.png")

    current = window.data
    assert current is not None and current.analysis is not None
    analysis = current.analysis
    combined = analysis.forces.smoothed.combined
    assert combined is not None
    values = combined.values.copy()
    values[2] = np.nan
    valid = list(combined.valid_rows)
    valid[2] = False
    missing = replace(
        analysis,
        forces=replace(
            analysis.forces,
            smoothed=replace(
                analysis.forces.smoothed,
                combined=SampleValues(values, valid_rows=valid),
            ),
        ),
    )
    window.data = current.with_analysis(missing)
    window.set_combined_view(True)
    assert len(window.plot.combined_series) == 2
    first, second = window.plot.combined_series
    assert first.points()[-1].x() == current.time_at(1)
    assert second.points()[0].x() == current.time_at(3)
    values[:] = np.nan
    unavailable = replace(
        missing,
        forces=replace(
            missing.forces,
            smoothed=replace(
                missing.forces.smoothed,
                combined=SampleValues(values, valid_rows=[False] * current.count),
            ),
        ),
    )
    window.data = current.with_analysis(unavailable)
    window.set_combined_view(True)
    assert not window.combined_toggle.isEnabled()
    assert not window.plot.combined_series
    assert len(window.plot.series) == 3
