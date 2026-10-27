"""Preview transport refreshes export geometry without opening another application."""

# cspell:words pixmap qapp

from dataclasses import replace
from PySide6.QtCore import QThread, QThreadPool, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QToolButton, QWidget

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    ExportLayout,
    ExportSettings,
    VideoAspect,
)
from ride_forces_analyzer.rendering.preview import ExportPreview, PreviewBackground
from ride_forces_analyzer.ui.exports.preview import PreviewView, preview_pixmap
from ride_forces_analyzer.ui.exports.preview_controller import PreviewController
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


def wait_for_preview(controller: PreviewController) -> ExportPreview:
    wait_until(lambda: controller.result is not None)
    result = controller.result
    assert result is not None
    return result


def test_preview_refresh_and_views_preserve_layout_format_and_extent_geometry(
    qapp: QApplication,
    small_preview_frames: None,
) -> None:
    application = qapp
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    assert isinstance(data, ExplorerData) and data.analysis is not None

    parent = QWidget()
    view = PreviewView()
    view.setParent(parent)
    view.resize(600, 400)
    thumbnail = QToolButton(parent)
    thumbnail.setIconSize(QSize(144, 81))
    controller = PreviewController(parent)
    delivered: list[QThread] = []

    def delivered_preview(_result: object) -> None:
        delivered.append(QThread.currentThread())

    controller.ready.connect(delivered_preview)
    settings = ExportSettings(layout=ExportLayout.ORBIT)
    content = replace(settings, extent=ExportExtent.CONTENT_AREA)
    portrait = replace(content, aspect=VideoAspect.PORTRAIT)
    cases = [
        (settings, (960, 540)),
        (content, (540, 540)),
        (portrait, (540, 540)),
        (replace(portrait, layout=ExportLayout.RIBBON), (540, 720)),
        (replace(portrait, layout=ExportLayout.HUD, extent=ExportExtent.FULL_FRAME), (540, 960)),
    ]
    try:
        for revision, (request, expected_size) in enumerate(cases, start=1):
            controller.schedule(
                data.analysis,
                request,
                3600,
                3609,
                3600,
                PreviewBackground.DARK,
                {},
            )
            assert controller.result is None and controller.revision == revision
            result = wait_for_preview(controller)
            selected = next(
                profile for profile in result.profiles if profile.layout == request.layout
            )
            assert selected.image.size == expected_size
            hud = next(profile for profile in result.profiles if profile.layout == ExportLayout.HUD)
            assert hud.image.size == (
                (960, 540) if request.aspect is VideoAspect.LANDSCAPE else (540, 960)
            )
            view.show_image(selected.image)
            assert (view.source.width(), view.source.height()) == expected_size
            thumbnail.setIcon(QIcon(preview_pixmap(selected.image)))
            icon = thumbnail.icon().pixmap(thumbnail.iconSize())
            for pixmap in (icon, view.pixmap()):
                assert not pixmap.isNull()
                assert abs(
                    pixmap.width() * expected_size[1] - pixmap.height() * expected_size[0],
                ) <= max(expected_size)
            assert len(delivered) == revision
        assert all(thread == application.thread() for thread in delivered)
    finally:
        controller.close()
        QThreadPool.globalInstance().waitForDone()
        parent.deleteLater()
        QApplication.processEvents()
