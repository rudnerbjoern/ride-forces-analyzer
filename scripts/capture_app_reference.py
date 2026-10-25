"""Capture fixed native Windows workspace and export-assistant reference images.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words dpiawareness Segoe Pixmap

import argparse
from collections.abc import Callable
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tomllib
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from PySide6.QtCharts import QCategoryAxis
from PySide6.QtCore import QPoint, QRect, QThreadPool, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget
from PIL import ImageGrab

from ride_forces_analyzer import __version__
from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.storage.preferences import Appearance
from ride_forces_analyzer.ui.exports.video import ExportDialog
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/real/VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces"
SOURCE_SHA256 = "f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04"
SAMPLE = 4960
SELECTION = (4200, 5100)
SMOOTHING = 11
WORKSPACE_SIZE = (1600, 1100)
APPEARANCE_SIZE = (800, 650)
EXPORT_SIZE = (1500, 1000)


def wait_for(application: QApplication, ready: Callable[[], bool]) -> None:
    """Process native Qt events until a capture condition succeeds or times out.

    Args:
        application: Native Qt application whose event loop owns the widgets.
        ready: Predicate reporting whether the captured view has settled.

    Returns:
        None.

    Raises:
        RuntimeError: Native screenshot preparation timed out.
    """
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
    """Capture the settled native widget to the requested PNG path.

    Args:
        application: Native Qt application whose event loop owns the widgets.
        widget: Qt object whose presentation is being changed or captured.
        target: Destination of the requested operation.

    Returns:
        None.

    Raises:
        RuntimeError: If the supplied settings or operation state are invalid.
    """
    focus = application.focusWidget()
    if focus is not None:
        focus.clearFocus()
    application.processEvents()
    if not widget.grab().save(str(target)):
        raise RuntimeError(f"Cannot save reference image: {target.name}")
    print(f"Captured {target.name}: sample {SAMPLE}", flush=True)


def capture_details(application: QApplication, window: ExplorerWindow, output: Path) -> None:
    """Capture real chart/card crops from fixed scenes in three original recordings.

    Args:
        application: Native Qt application whose event loop owns the widgets.
        window: Explorer window whose current state is being captured.
        output: Output directory or path for generated artifacts.

    Returns:
        None.

    Raises:
        OSError: If the required filesystem operation fails.
        ValueError: Detail source hash differs from the fixed reference recording.
            Original detail recording changed during capture.
        RuntimeError: If the supplied settings or operation state are invalid. Cannot
            capture airtime chart and legend. Missing force value card. Cannot capture
            force cards. Missing calibrated force axis. Cannot capture smoothing
            comparison.
    """
    scenes = (
        ("VoltronNevera", 4960, (4500, 5250)),
        ("Taron", 3399, (3250, 3500)),
        ("Manta", 4782, (4650, 4900)),
    )
    hashes = {
        "VoltronNevera": SOURCE_SHA256,
        "Taron": "cfa03821140aaa76c52e1bb69905db96a775a5d6772741b5d3a90f48a4254564",
        "Manta": "1d06e636b0cd26c7634503bf3f5f93e1906791ce47028c129af1c1828c7b268c",
    }
    sources = {name: next(SOURCE.parent.glob(name + "-*.forces")) for name, _, _ in scenes}
    for name, source in sources.items():
        if sha256(source.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError("Detail source hash differs from the fixed reference recording")
    output.mkdir(parents=True, exist_ok=True)
    window.setMinimumSize(1280, 720)
    window.resize(1280, 720)
    window.set_appearance(0)
    manifest: dict[str, object] = {}
    try:
        for name, sample, interval in scenes:
            window.open_path(sources[name])
            wait_for(application, window.open_action.isEnabled)
            if window.data is None or not window.data.calibration_available:
                raise RuntimeError(f"Cannot load calibrated {name} reference")
            window.reference_toggle.setChecked(True)
            window.navigation.slider.setValue(sample)
            # Keep the selection highlight outside the illustrated interval.
            window.inspector.last.setValue(0)
            window.inspector.first.setValue(0)
            time_range = tuple(window.data.time_at(index) for index in interval)
            window.plot.axis_x.setRange(*time_range)
            wait_for(application, lambda: True)
            # Refresh labels once the compact layout has settled after the zoom.
            window.plot.axis_x.setRange(time_range[0] + 0.02, time_range[1])
            window.plot.axis_x.setRange(*time_range)
            wait_for(application, lambda: True)
            details: dict[str, object] = {
                "source_sha256": hashes[name],
                "sample": sample,
                "replay": window.data.replay_text(sample),
                "interval": interval,
                "smoothing": SMOOTHING,
            }
            if name == "VoltronNevera":
                bounds = window.plot.chart_view.geometry().united(window.plot.airtime_legend.geometry())
                parent = window.plot.chart_view.parentWidget()
                if parent is None or not parent.grab(bounds).save(
                    str(output / "voltron-airtime-detail.png"),
                ):
                    raise RuntimeError("Cannot capture airtime chart and legend")
                details["contexts"] = sorted(
                    {
                        context_label
                        for index in range(*interval)
                        if (context_label := window.data.vertical_context_label(index)) is not None
                    },
                )
            elif name == "Taron":
                bounds = QRect()
                for value_label in window.navigation.value_labels:
                    card = value_label.parentWidget()
                    if card is None:
                        raise RuntimeError("Missing force value card")
                    bounds = bounds.united(QRect(card.mapTo(window, QPoint()), card.size()))
                if not window.grab(bounds).save(str(output / "taron-force-cards.png")):
                    raise RuntimeError("Cannot capture force cards")
                details["cards"] = window.data.sample_cards(sample)
            else:
                for checkbox in window.visibility[1:]:
                    checkbox.setChecked(False)
                panels: list[QPixmap] = []
                scales: list[dict[str, object]] = []
                force_range: tuple[float, float] | None = None
                force_labels: list[tuple[str, float]] = []
                for smoothing in (1, 11, 31):
                    window.inspector.smoothing_slider.setValue(smoothing // 2)
                    wait_for(
                        application,
                        lambda: (
                            window.data is not None and window.data.smoothing_window == smoothing
                        ),
                    )
                    if force_range is None:
                        force_range = (window.plot.axis_y.min(), window.plot.axis_y.max())
                        if not isinstance(window.plot.axis_y, QCategoryAxis):
                            raise RuntimeError("Missing calibrated force axis")
                        force_labels = [
                            (label, window.plot.axis_y.endValue(label))
                            for label in window.plot.axis_y.categoriesLabels()
                        ]
                    # Lock the comparison scale, including category labels. The normal
                    # workspace intentionally rescales after a smoothing change.
                    axis = window.plot.axis_y
                    if not isinstance(axis, QCategoryAxis):
                        raise RuntimeError("Missing calibrated force axis")
                    axis.blockSignals(True)
                    try:
                        for label in axis.categoriesLabels():
                            axis.remove(label)
                        axis.setStartValue(force_range[0])
                        for label, value in force_labels:
                            axis.append(label, value)
                        axis.setRange(*force_range)
                    finally:
                        axis.blockSignals(False)
                    window.plot.axis_x.setRange(*time_range)
                    window.plot.sample_cursor.hide()
                    wait_for(application, lambda: True)
                    panels.append(window.plot.chart_view.grab())
                    scales.append(
                        {
                            "smoothing": smoothing,
                            "force_range": (axis.min(), axis.max()),
                            "time_range": (window.plot.axis_x.min(), window.plot.axis_x.max()),
                        },
                    )
                width = panels[0].width()
                heading_height = 32
                height = sum(panel.height() + heading_height for panel in panels)
                comparison = QPixmap(width, height)
                comparison.fill(QColor(window.theme.panel))
                painter = QPainter(comparison)
                try:
                    painter.setFont(QFont("Segoe UI", 11))
                    painter.setPen(QColor(window.theme.text))
                    top = 0
                    for title, panel in zip(
                        (
                            "1 sample - no smoothing",
                            "11 samples - default",
                            "31 samples - stronger smoothing",
                        ),
                        panels,
                        strict=True,
                    ):
                        painter.drawText(16, top + 23, title)
                        painter.drawPixmap(0, top + heading_height, panel)
                        top += panel.height() + heading_height
                finally:
                    painter.end()
                if not comparison.save(str(output / "manta-smoothing-comparison.png")):
                    raise RuntimeError("Cannot capture smoothing comparison")
                details["smoothing"] = (1, 11, 31)
                details["force_range"] = force_range
                details["time_range"] = time_range
                details["panels"] = scales
            manifest[name] = details
            print(f"Captured {name} detail: sample {sample}", flush=True)
        (output / "readme-reference.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    finally:
        for name, source in sources.items():
            if sha256(source.read_bytes()).hexdigest() != hashes[name]:
                raise ValueError("Original detail recording changed during capture")


def capture_reference(output: Path, *, details: bool = False, themes: bool = False) -> None:
    """Capture the fixed native reference scene with isolated application state.

    Args:
        output: Output directory or path for generated artifacts.
        details: Whether to capture the fixed README detail scenes.
        themes: Whether to capture the fixed appearance gallery.

    Returns:
        None.

    Raises:
        ValueError: If the supplied settings or operation state are invalid. Voltron
            source hash differs from the fixed reference recording. Original Voltron
            recording changed during capture.
        RuntimeError: Capture requires native Windows with a desktop session. Run
            screenshot capture in a separate Python process. Cannot load calibrated
            Voltron reference.
        OSError: If the required filesystem operation fails.
    """
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project_version = tomllib.load(stream)["project"]["version"]
    if __version__ != project_version:
        raise ValueError(
            f"Screenshot version {__version__} differs from project version {project_version}",
        )
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
            window = ExplorerWindow(AppSettings(language=Language.ENGLISH))
            dialog: ExportDialog | None = None
            try:
                window.setMinimumSize(*WORKSPACE_SIZE)
                window.resize(*WORKSPACE_SIZE)
                window.show()
                handle = window.windowHandle()
                wait_for(application, handle.isExposed)
                if details:
                    capture_details(application, window, output)
                    return
                window.open_path(SOURCE)
                wait_for(application, window.open_action.isEnabled)
                if window.data is None or not window.data.calibration_available:
                    raise RuntimeError("Cannot load calibrated Voltron reference")
                window.reference_toggle.setChecked(True)
                window.inspector.smoothing_slider.setValue(SMOOTHING // 2)
                window.inspector.first.setValue(SELECTION[0])
                window.inspector.last.setValue(SELECTION[1])
                window.navigation.slider.setValue(SAMPLE)
                window.reset_view()
                output.mkdir(parents=True, exist_ok=True)
                if themes:
                    images: dict[str, str] = {}
                    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                    window.show()
                    window.setMinimumSize(0, 0)
                    window.resize(*APPEARANCE_SIZE)
                    for index, appearance in enumerate(Appearance):
                        if appearance is Appearance.SYSTEM:
                            continue
                        window.set_appearance(index)
                        wait_for(application, lambda: window.theme.name is appearance)
                        filename = f"appearance-{appearance.value}.png"
                        window.raise_()
                        window.activateWindow()
                        wait_for(application, lambda: True)
                        focus = application.focusWidget()
                        if focus is not None:
                            focus.clearFocus()
                        application.processEvents()
                        frame = window.frameGeometry()
                        ImageGrab.grab(
                            bbox=(
                                frame.left(),
                                frame.top(),
                                frame.right() + 1,
                                frame.bottom() + 1,
                            ),
                            all_screens=True,
                        ).save(output / filename)
                        print(f"Captured {filename}: sample {SAMPLE}", flush=True)
                        images[appearance.value] = filename
                    (output / "appearance-reference.json").write_text(
                        json.dumps(
                            {
                                "source_sha256": SOURCE_SHA256,
                                "sample": SAMPLE,
                                "replay": window.data.replay_text(SAMPLE),
                                "selection": SELECTION,
                                "smoothing": SMOOTHING,
                                "language": "en",
                                "font": "Segoe UI 9 pt",
                                "scale_factor": 1,
                                "workspace_size": APPEARANCE_SIZE,
                                "includes_window_frame": True,
                                "themes": images,
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    return
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
                dialog.form.layout_profile.setCurrentIndex(0)
                dialog.form.position.setCurrentIndex(
                    dialog.form.position.findData(LayoutPosition.BOTTOM.value),
                )
                dialog.form.aspect.setCurrentIndex(0)
                dialog.form.overlay_language.setCurrentIndex(0)
                dialog.form.mode.setCurrentIndex(0)
                dialog.form.interval.setCurrentIndex(0)
                dialog.form.smoothing.setCurrentIndex(SMOOTHING // 2)
                dialog.form.flip_vertical.setChecked(True)
                dialog.form.flip_lateral.setChecked(False)
                dialog.form.gpu.setChecked(True)
                dialog.background.setCurrentIndex(0)
                dialog.form.fps.setCurrentText("50")
                dialog.form.seconds.setValue(12)
                dialog.form.encoder.setText(".tmp/ffmpeg/bin/ffmpeg.exe")
                dialog.show()
                preview_dialog = dialog
                wait_for(
                    application,
                    lambda: (
                        preview_dialog.previews.result is not None
                        and preview_dialog.previews.worker is None
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
                    "position": dialog.form.position.currentData(),
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
    """Run this module's application or command-line entry point.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/images",
        help="Destination for the selected reference images and settings manifest",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--details",
        action="store_true",
        help="Capture the three README detail images instead",
    )
    mode.add_argument(
        "--themes",
        action="store_true",
        help="Capture each workspace theme except System for the appearance guide instead",
    )
    arguments = parser.parse_args()
    capture_reference(arguments.output, details=arguments.details, themes=arguments.themes)


if __name__ == "__main__":
    main()
