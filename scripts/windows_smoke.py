"""Exercise the actual frozen GUI, import, renderer and optional bundled encoder.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Über

import json
from pathlib import Path
import sys
from time import monotonic, sleep
import traceback

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication

from ride_forces_analyzer import __version__
from ride_forces_analyzer.config import AppSettings
from ride_forces_analyzer.rendering.encoding import export_video, find_ffmpeg
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.model import ExportSettings, prepare_export
from ride_forces_analyzer.ui.window import ExplorerWindow


def smoke_test(
    report: Path,
    recording: Path | None,
    with_ffmpeg: bool,
    ffmpeg: Path | None = None,
) -> None:
    """Exercise native GUI startup, reference import, rendering and optional encoding.

    Args:
        report: Path for the local JSON verification report.
        recording: Optional recording path to open.
        with_ffmpeg: Whether the smoke check must execute a real video encode.
        ffmpeg: Explicit encoder executable; None permits the documented discovery policy.

    Returns:
        None.

    Raises:
        OSError: If the required filesystem operation fails.
        BaseException: If the underlying operation fails; the original error is
            propagated.
    """
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    application = QApplication([])
    window: ExplorerWindow | None = None
    result: dict[str, object] = {"version": __version__, "passed": False}
    try:
        if getattr(sys, "frozen", False):
            assert b"pdf" not in QImageReader.supportedImageFormats()
            result["pdf_plugin_absent"] = True
        window = ExplorerWindow(AppSettings(language="en"))
        window.show()
        deadline = monotonic() + 10
        while not window.windowHandle().isExposed() and monotonic() < deadline:
            application.processEvents()
            sleep(0.001)
        assert window.isVisible() and window.windowHandle().isExposed()
        result["gui"] = True
        window.set_ui_language(1)
        window.set_appearance(1)
        application.processEvents()
        assert window.theme.name == "light" and window.about_action.text() == "Über …"
        result["german_light"] = True
        if recording is not None:
            window.open_path(recording.resolve())
            deadline = monotonic() + 30
            while not window.open_action.isEnabled() and monotonic() < deadline:
                application.processEvents()
                sleep(0.001)
            assert window.data is not None, window.statusBar().currentMessage()
            result["samples"] = window.data.count
            assert window.data.analysis is not None
            timeline = prepare_export(
                window.data.analysis,
                ExportSettings(
                    layout="orbit",
                    language="de",
                    prefer_gpu=False,
                    output="opaque",
                    fps=25,
                ),
                0,
                2,
            )
            image = OverlayRenderer(timeline).render_frame(0)
            assert image.size == (3840, 2160)
            result["render"] = True
            if with_ffmpeg:
                encoder = find_ffmpeg(ffmpeg)
                result["encoder"] = str(encoder.name)
                if ffmpeg is None:
                    result["bundled_encoder"] = str(encoder.name)
                output = report.with_suffix(".mp4")
                export_video(timeline, output, ffmpeg=encoder)
                assert output.is_file() and output.stat().st_size > 0
                result["encode"] = True
        result["passed"] = True
    except BaseException:
        result["error"] = traceback.format_exc()
        raise
    finally:
        if window is not None:
            window.close()
        QThreadPool.globalInstance().waitForDone()
        application.processEvents()
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
