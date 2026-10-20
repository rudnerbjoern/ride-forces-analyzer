"""Capture fixed native Windows workspace and export-assistant reference images.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words dpiawareness Segoe

import argparse
from collections.abc import Callable
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

from ride_forces_analyzer.config import AppSettings
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.window import ExplorerWindow

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/real/VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces"
SOURCE_SHA256 = "f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04"
SAMPLE = 4960
SELECTION = (4200, 5100)
SMOOTHING = 11
WORKSPACE_SIZE = (1600, 1100)
EXPORT_SIZE = (1500, 1000)


def wait_for(application: QApplication, ready: Callable[[], bool]) -> None:
    deadline = monotonic() + 90
    while not ready():
        if monotonic() > deadline:
            raise RuntimeError("Native screenshot preparation timed out")
        application.processEvents()
        sleep(0.01)
    # Let queued layout/paint updates settle after workers have delivered their result.
    for _ in range(20):
        application.processEvents()
        sleep(0.01)


def save_widget(application: QApplication, widget: QWidget, target: Path) -> None:
    focus = application.focusWidget()
    if focus is not None:
        focus.clearFocus()
    application.processEvents()
    if not widget.grab().save(str(target)):
        raise RuntimeError(f"Cannot save reference image: {target.name}")
    print(f"Captured {target.name}: sample {SAMPLE}", flush=True)


def capture_reference(output: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Capture requires native Windows with a desktop session")
    if sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Voltron source hash differs from the fixed reference recording")
    if QApplication.instance() is not None:
        raise RuntimeError("Run screenshot capture in a separate Python process")
    output = output.resolve()
    temporary = ROOT / ".tmp"
    temporary.mkdir(exist_ok=True)
    previous_directory = Path.cwd()
    environment = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "QT_SCALE_FACTOR")}
    try:
        os.chdir(ROOT)
        with TemporaryDirectory(dir=temporary, prefix="app-reference-") as profile:
            os.environ["LOCALAPPDATA"] = profile
            os.environ["QT_SCALE_FACTOR"] = "1"
            arguments = ["capture_app_reference", "-platform", "windows:dpiawareness=0"]
            application = QApplication(arguments)
            application.setFont(QFont("Segoe UI", 9))
            window = ExplorerWindow(AppSettings(language="en"))
            dialog: ExportDialog | None = None
            try:
                window.setMinimumSize(*WORKSPACE_SIZE)
                window.resize(*WORKSPACE_SIZE)
                window.show()
                handle = window.windowHandle()
                wait_for(application, handle.isExposed)
                window.open_path(SOURCE)
                wait_for(application, window.open_action.isEnabled)
                if window.data is None or not window.data.calibration_available:
                    raise RuntimeError("Cannot load calibrated Voltron reference")
                window.reference_toggle.setChecked(True)
                window.smoothing_slider.setValue(SMOOTHING // 2)
                window.first.setValue(SELECTION[0])
                window.last.setValue(SELECTION[1])
                window.slider.setValue(SAMPLE)
                window.reset_view()
                output.mkdir(parents=True, exist_ok=True)
                for appearance, name in ((0, "dark"), (1, "light")):
                    window.set_appearance(appearance)
                    wait_for(application, lambda: window.theme.name == name)
                    save_widget(application, window, output / f"workspace-{name}.png")
                dialog = ExportDialog(
                    window.data,
                    *SELECTION,
                    window,
                    current_sample=SAMPLE,
                    store=ExportStore(Path(profile) / "exports.sqlite3"),
                )
                dialog.setMinimumSize(*EXPORT_SIZE)
                dialog.resize(*EXPORT_SIZE)
                dialog.layout_profile.setCurrentIndex(0)
                dialog.aspect.setCurrentIndex(0)
                dialog.overlay_language.setCurrentIndex(0)
                dialog.mode.setCurrentIndex(0)
                dialog.interval.setCurrentIndex(0)
                dialog.smoothing.setCurrentIndex(SMOOTHING // 2)
                dialog.flip_vertical.setChecked(True)
                dialog.flip_lateral.setChecked(False)
                dialog.gpu.setChecked(True)
                dialog.background.setCurrentIndex(0)
                dialog.fps.setCurrentText("50")
                dialog.seconds.setValue(12)
                dialog.encoder.setText(".tmp/ffmpeg/bin/ffmpeg.exe")
                dialog.show()
                preview_dialog = dialog
                wait_for(
                    application,
                    lambda: (
                        preview_dialog.preview_result is not None
                        and preview_dialog.preview_worker is None
                    ),
                )
                save_widget(application, dialog, output / "export-preview.png")
                manifest = {
                    "source_sha256": SOURCE_SHA256,
                    "sample": SAMPLE,
                    "replay": window.data.replay_text(SAMPLE),
                    "selection": SELECTION,
                    "smoothing": SMOOTHING,
                    "language": "en",
                    "font": "Segoe UI 9 pt",
                    "scale_factor": 1,
                    "workspace_size": WORKSPACE_SIZE,
                    "export_size": EXPORT_SIZE,
                    "layout": "ribbon",
                    "aspect": "landscape",
                    "output": "transparent",
                    "fps": 50,
                    "window_seconds": 12,
                }
                (output / "app-reference.json").write_text(
                    json.dumps(manifest, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            finally:
                if dialog is not None:
                    dialog.close()
                window.close()
                QThreadPool.globalInstance().waitForDone()
                application.processEvents()
    finally:
        os.chdir(previous_directory)
        for key, value in environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
            raise ValueError("Original Voltron recording changed during capture")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/images",
        help="Destination; replaces the three named screenshots and app-reference.json",
    )
    capture_reference(parser.parse_args().output)


if __name__ == "__main__":
    main()
