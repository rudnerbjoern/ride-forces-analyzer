"""Offline FFmpeg encoding with bounded memory, cancellation and exclusive publication.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words colorspace creationflags ENOTSUP EXDEV faststart hwupload lavfi libx movflags nostdin nvenc prores qscale rawvideo yuva

from collections.abc import Callable
from pathlib import Path
import json
import errno
import os
import shutil
import subprocess
import sys
from threading import Event
from uuid import uuid4

from .frames import OverlayRenderer
from .layouts import export_region
from .model import ExportTimeline


class ExportCancelled(Exception):
    """The user cancelled before a completed output was published."""


def find_ffmpeg(explicit: Path | None = None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise ValueError("Choose an existing FFmpeg executable")
        return explicit.resolve()
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).resolve().parent / "ffmpeg.exe"
        if bundled.is_file():
            return bundled
    executable = shutil.which("ffmpeg")
    if executable:
        return Path(executable)
    local = Path.cwd() / ".tmp/ffmpeg/bin/ffmpeg.exe"
    if local.is_file():
        return local.resolve()
    raise ValueError("FFmpeg was not found. Choose ffmpeg.exe in the export dialog.")


def encoder_command(
    ffmpeg: Path,
    timeline: ExportTimeline,
    target: Path,
    *,
    use_gpu: bool = False,
) -> list[str]:
    transparent = timeline.settings.output == "transparent"
    codec = (
        [
            "-c:v",
            "prores_ks_vulkan" if use_gpu else "prores_ks",
            "-profile:v",
            "4444",
            *([] if use_gpu else ["-qscale:v", "4"]),
            "-pix_fmt",
            "vulkan" if use_gpu else "yuva444p10le",
            "-alpha_bits",
            "16",
        ]
        if transparent
        else (
            ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "18", "-pix_fmt", "yuv420p"]
            if use_gpu
            else ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"]
        )
    )
    alpha = "0" if transparent else "1"
    device = (
        ["-init_hw_device", "vulkan=overlay_gpu:NVIDIA", "-filter_hw_device", "overlay_gpu"]
        if use_gpu and transparent
        else []
    )
    x, y, width, height = export_region(timeline.settings)
    canvas_width, canvas_height = timeline.settings.dimensions
    filters = f"pad={canvas_width}:{canvas_height}:{x}:{y}:color=black@{alpha}"
    if use_gpu and transparent:
        filters += ",setparams=colorspace=bt709,hwupload,scale_vulkan=format=yuva444p10le:out_range=tv,setparams=colorspace=bt709"
    return [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-n",
        *device,
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgba",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        str(timeline.settings.fps),
        "-i",
        "pipe:0",
        "-an",
        "-vf",
        filters,
        "-metadata",
        "comment="
        + json.dumps(
            {
                "source_sha256": timeline.source_sha256,
                "sample_rate": timeline.sample_rate,
                "video_fps": timeline.settings.fps,
                "first_sample": timeline.first,
                "last_sample_inclusive": timeline.last,
                "replay_origin": timeline.replay_origin,
                "smoothing_window": timeline.smoothing_window,
                "time_basis": "INFERRED_UNIFORM",
                "gpu_encoding": use_gpu,
                "layout": timeline.settings.layout,
                "aspect": timeline.settings.aspect,
                "language": timeline.settings.language,
                "orientation": "angle-source-gravity-to-stored-vertical-v1",
            },
            sort_keys=True,
        ),
        *codec,
        "-threads",
        "4",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-color_range",
        "tv",
        "-movflags",
        "+faststart",
        str(target),
    ]


def supports_nvidia(ffmpeg: Path, timeline: ExportTimeline) -> bool:
    """Probe a real GPU encode; compiled-in codec names alone are not evidence."""
    if not timeline.settings.prefer_gpu:
        return False
    transparent = timeline.settings.output == "transparent"
    device = (
        ["-init_hw_device", "vulkan=overlay_gpu:NVIDIA", "-filter_hw_device", "overlay_gpu"]
        if transparent
        else []
    )
    codec = (
        [
            "-vf",
            "format=yuva444p10le,hwupload",
            "-c:v",
            "prores_ks_vulkan",
            "-profile:v",
            "4",
            "-alpha_bits",
            "16",
        ]
        if transparent
        else ["-c:v", "h264_nvenc"]
    )
    try:
        result = subprocess.run(
            [
                str(ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                *device,
                "-f",
                "lavfi",
                "-i",
                "color=black:s=128x128,format=rgba",
                "-frames:v",
                "1",
                *codec,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=30,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0,
        )
        return result.returncode == 0
    except OSError, subprocess.TimeoutExpired:
        return False


def export_video(
    timeline: ExportTimeline,
    destination: Path,
    *,
    ffmpeg: Path | None = None,
    cancelled: Event | None = None,
    progress: Callable[[int, int], None] | None = None,
    status: Callable[[str], None] | None = None,
) -> Path:
    """Publish one complete 4K video. Never overwrite existing files or source data."""
    extension = ".mov" if timeline.settings.output == "transparent" else ".mp4"
    destination = destination.resolve()
    if destination.suffix.lower() != extension:
        raise ValueError(f"This output requires a {extension} filename")
    if destination.exists():
        raise ValueError("Output already exists; choose a new filename")
    executable = find_ffmpeg(ffmpeg)
    cancellation = cancelled if cancelled is not None else Event()
    if cancellation.is_set():
        raise ExportCancelled()
    use_gpu = supports_nvidia(executable, timeline)
    if status is not None:
        status(
            "Encoding on NVIDIA GPU"
            if use_gpu
            else "Encoding on CPU (GPU unavailable or disabled)",
        )
    if cancellation.is_set():
        raise ExportCancelled()
    staging = Path.cwd() / ".tmp" / f"video-export-{uuid4().hex}"
    staging.mkdir(parents=True)
    process: subprocess.Popen[bytes] | None = None
    published = False
    created_destination = False
    try:
        target = staging / f"output{extension}"
        renderer = OverlayRenderer(timeline)
        with (staging / "encoder.log").open("w+b") as log:
            process = subprocess.Popen(
                encoder_command(executable, timeline, target, use_gpu=use_gpu),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0,
            )
            assert process.stdin is not None
            try:
                for frame in range(timeline.frame_count):
                    if cancellation.is_set():
                        raise ExportCancelled()
                    process.stdin.write(renderer.render_region(frame).tobytes())
                    if progress is not None:
                        progress(frame + 1, timeline.frame_count)
                process.stdin.close()
                code = process.wait(timeout=120)
            except BrokenPipeError as error:
                process.wait(timeout=10)
                log.seek(0)
                raise RuntimeError(log.read()[-4000:].decode("utf-8", errors="replace")) from error
            if code != 0:
                log.seek(0)
                raise RuntimeError(log.read()[-4000:].decode("utf-8", errors="replace"))
        if cancellation.is_set():
            raise ExportCancelled()
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError("Encoder produced no video")
        try:
            os.link(target, destination)
        except OSError as error:
            if error.errno not in (errno.EXDEV, errno.EPERM, errno.ENOTSUP):
                raise
        else:
            published = True
            return destination
        with destination.open("xb") as output:
            created_destination = True
            with target.open("rb") as encoded:
                while block := encoded.read(1024 * 1024):
                    if cancellation.is_set():
                        raise ExportCancelled()
                    output.write(block)
        published = True
        return destination
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            if process.stdin is not None and not process.stdin.closed:
                try:
                    process.stdin.close()
                except OSError:
                    pass
        if created_destination and not published:
            destination.unlink(missing_ok=True)
        shutil.rmtree(staging)
