"""Missing data and defensive model boundaries use production drawing without encoding."""

# cspell:words getbbox WINDIR

from dataclasses import replace
from pathlib import Path

import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.layouts.ribbon import RibbonRenderer
from ride_forces_analyzer.rendering.layouts.column import ColumnRenderer
from ride_forces_analyzer.rendering.layouts.common import Drawing
from ride_forces_analyzer.rendering.layouts.hud import HudRenderer
from ride_forces_analyzer.rendering.layouts.orbit import OrbitRenderer
from ride_forces_analyzer.rendering.model import ExportLayout, ExportSettings, prepare_export
from ride_forces_analyzer.rendering.peaks import PeakEnvelope
from ride_forces_analyzer.rendering.size_estimate import estimate_size_bytes


def test_layout_histories_and_current_markers_accept_missing_samples(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    for layout, kind in (
        (ExportLayout.COLUMN, ColumnRenderer),
        (ExportLayout.RIBBON, RibbonRenderer),
        (ExportLayout.ORBIT, OrbitRenderer),
    ):
        timeline = prepare_export(manta.analysis, ExportSettings(layout=layout), 0, 4)
        channels = tuple(
            replace(channel, values=(0.2, 0.4, None, None, 0.6)) for channel in timeline.channels
        )
        timeline = replace(timeline, channels=channels)
        renderer = kind(timeline)
        image = renderer.render_position(2)
        assert image.mode == "RGBA" and image.getbbox() is not None
        if isinstance(renderer, ColumnRenderer):
            assert renderer.render_column(0).size == image.size


def test_generic_drawing_requires_a_concrete_renderer_and_hud_supports_missing_fonts(
    manta: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=ExportLayout.HUD), 0, 0)
    with pytest.raises(NotImplementedError):
        Drawing(timeline, 16, 16).render(0)
    monkeypatch.setenv("WINDIR", str(export_directory / "missing-font-directory"))
    renderer = HudRenderer(timeline)
    assert renderer.base.size == timeline.settings.dimensions


def test_window_size_peak_gaps_and_wide_scale_boundaries(manta: ExplorerData) -> None:
    for seconds in (0.0, 61.0, float("nan")):
        with pytest.raises(ValueError, match="Visible time window"):
            ExportSettings(window_seconds=seconds)
    for count, rate in ((0, 50.0), (1, 0.0)):
        with pytest.raises(ValueError, match="positive sample count and sample rate"):
            estimate_size_bytes(ExportSettings(), count, rate)
    envelope = PeakEnvelope.prepare((None,), 0, 0, 50)
    assert envelope.at(0, None) == (0.0, 0.0)
    assert envelope.at(0, 0.8) == (0.8, 0.0)
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(), 0, 0)
    channel = replace(timeline.channels[0], low=-20.0, high=20.0)
    assert channel.ticks == (-20.0, -1.0, 0.0, 1.0, 20.0)


def test_export_rejects_a_snapshot_with_missing_rate(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    snapshot = replace(manta.analysis)
    time = replace(snapshot.time)
    basis = replace(time.basis)
    # Corrupt only owned test copies to exercise the boundary's defensive guard.
    object.__setattr__(basis, "sample_rate", None)
    object.__setattr__(time, "basis", basis)
    object.__setattr__(snapshot, "time", time)
    with pytest.raises(ValueError, match="Export requires a sample rate"):
        prepare_export(snapshot, ExportSettings(), 0, 0)
