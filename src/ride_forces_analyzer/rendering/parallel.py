"""Ordered, bounded frame generation with independent renderers per worker thread.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words buffersize

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from threading import local
from typing import cast

from ride_forces_analyzer.cpu_resources import effective_render_jobs
from .frames import OverlayRenderer
from .model import ExportTimeline


def render_region_bytes(timeline: ExportTimeline, jobs: int = 1) -> Generator[bytes, None, None]:
    """Yield encoder-ready regions in frame order, with bounded outstanding work.

    One job uses the direct serial path. Parallel workers share only the immutable
    timeline; each owns its Pillow images and fonts. The submission buffer is
    limited to the worker count, plus the frame currently being yielded.
    Closing the iterator cancels queued work and joins active frame renders.

    Args:
        timeline: Bound video timeline containing the source interval and export settings.
        jobs: Requested number of concurrent frame renderers.

    Yields:
        Raw image bytes for each rendered frame, in output-frame order.

    Raises:
        ValueError: The requested renderer count is not a positive integer.
    """
    jobs = min(effective_render_jobs(jobs), timeline.frame_count)
    if jobs == 1:
        renderer = OverlayRenderer(timeline)
        for frame in range(timeline.frame_count):
            yield renderer.render_region(frame).tobytes()
        return

    state = local()

    def render(frame: int) -> bytes:
        renderer = cast(OverlayRenderer | None, getattr(state, "renderer", None))
        if renderer is None:
            renderer = OverlayRenderer(timeline)
            state.renderer = renderer
        return renderer.render_region(frame).tobytes()

    executor = ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="overlay-render")
    try:
        yield from executor.map(render, range(timeline.frame_count), buffersize=jobs)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
