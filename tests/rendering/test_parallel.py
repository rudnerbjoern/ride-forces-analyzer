"""Parallel frames remain ordered, bounded and identical to serial rendering."""

from contextlib import closing
from dataclasses import replace
from hashlib import sha256
from threading import Event, Thread, current_thread
from types import SimpleNamespace
from typing import cast

from PIL import Image
import pytest

from ride_forces_analyzer import cpu_resources
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering import parallel
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    ExportLayout,
    VideoAspect,
    ExportSettings,
    ExportTimeline,
    prepare_export,
)


@pytest.mark.parametrize(
    "settings",
    [
        ExportSettings(layout=ExportLayout.HUD),
        ExportSettings(
            layout=ExportLayout.HUD,
            aspect=VideoAspect.PORTRAIT,
            output=VideoOutput.OPAQUE,
        ),
        ExportSettings(layout=ExportLayout.RIBBON, output=VideoOutput.OPAQUE),
        ExportSettings(layout=ExportLayout.CORNERS, aspect=VideoAspect.PORTRAIT),
        ExportSettings(layout=ExportLayout.ORBIT),
        ExportSettings(
            layout=ExportLayout.COLUMN,
            aspect=VideoAspect.PORTRAIT,
            output=VideoOutput.OPAQUE,
        ),
    ],
    ids=lambda settings: f"{settings.layout}-{settings.aspect}-{settings.output}",
)
def test_parallel_pixels_match_serial_for_every_layout(
    manta: ExplorerData,
    settings: ExportSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    monkeypatch.setattr(cpu_resources, "render_job_limit", lambda: 4)
    timeline = prepare_export(manta.analysis, replace(settings, fps=60), 3600, 3602)
    serial = [sha256(frame).digest() for frame in parallel.render_region_bytes(timeline)]
    assert len(serial) == timeline.frame_count
    assert [sha256(frame).digest() for frame in parallel.render_region_bytes(timeline, 2)] == serial


@pytest.mark.parametrize("fail", [False, True])
def test_workers_are_independent_ordered_bounded_and_joined_on_close_or_failure(
    monkeypatch: pytest.MonkeyPatch,
    fail: bool,
) -> None:
    monkeypatch.setattr(cpu_resources, "render_job_limit", lambda: 4)
    second_frame = Event()
    owners: list[Thread] = []
    started: list[int] = []

    class Renderer:
        def __init__(self, timeline: ExportTimeline) -> None:
            self.owner = current_thread()
            owners.append(self.owner)

        def render_region(self, frame: int) -> Image.Image:
            assert current_thread() is self.owner
            started.append(frame)
            if frame == 0:
                assert second_frame.wait(5)
            if frame == 1:
                second_frame.set()
                if fail:
                    raise ValueError("render failed")
            return Image.new("RGBA", (1, 1), (frame, 0, 0, 255))

    monkeypatch.setattr(parallel, "OverlayRenderer", Renderer)
    timeline = cast(ExportTimeline, SimpleNamespace(frame_count=100))
    with closing(parallel.render_region_bytes(timeline, 2)) as frames:
        assert next(frames) == bytes((0, 0, 0, 255))
        assert len(started) <= 3  # Two buffered frames plus the yielded frame.
        if fail:
            with pytest.raises(ValueError, match="render failed"):
                next(frames)
        else:
            assert next(frames) == bytes((1, 0, 0, 255))
    assert len(owners) == 2
    assert all(not owner.is_alive() for owner in owners)


def test_one_job_uses_no_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_pool(*args: object, **kwargs: object) -> None:
        pytest.fail("A serial export must not start a thread pool")

    class Renderer:
        def __init__(self, timeline: ExportTimeline) -> None:
            pass

        def render_region(self, frame: int) -> Image.Image:
            return Image.new("RGBA", (1, 1), (frame, 0, 0, 255))

    monkeypatch.setattr(parallel, "ThreadPoolExecutor", no_pool)
    monkeypatch.setattr(parallel, "OverlayRenderer", Renderer)
    timeline = cast(ExportTimeline, SimpleNamespace(frame_count=2))
    assert list(parallel.render_region_bytes(timeline)) == [
        bytes((0, 0, 0, 255)),
        bytes((1, 0, 0, 255)),
    ]
