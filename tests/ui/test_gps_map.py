"""Explicit map requests stay independent of recordings and ignore stale workers."""

# cspell:words Kartenhintergrund laden Pixmap

from threading import Event

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem
import pytest

from ride_forces_analyzer.map_background import MapBackground, MapError, MapRequest
from ride_forces_analyzer.ui import gps
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


def background(request: MapRequest) -> MapBackground:
    image = QImage(request.width, request.height, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    return MapBackground(request, image)


def test_gps_map_requires_click_and_preserves_route_and_explorer_on_failure(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.gps_button.click()
    dialog = window.gps_window
    assert isinstance(dialog, gps.GpsDialog)
    requests: list[MapRequest] = []

    def load(request: MapRequest, cancelled: Event) -> MapBackground:
        requests.append(request)
        if len(requests) > 1:
            raise MapError("offline")
        return background(request)

    monkeypatch.setattr(gps, "load_background", load)
    QApplication.processEvents()
    assert not requests and dialog.map_item is None
    assert not dialog.attribution.isVisible()
    original = window.data
    sample = window.slider.value()
    bounds = (window.axis_x.min(), window.axis_x.max())
    route_items = tuple(dialog.view.scene().items())
    dialog.map_button.click()
    assert not dialog.map_button.isEnabled()
    wait_until(lambda: dialog.worker is None)
    assert dialog.map_item is not None
    item = dialog.map_item
    assert isinstance(item, QGraphicsPixmapItem)
    assert item.transformationMode() == Qt.TransformationMode.SmoothTransformation
    assert item.zValue() < min(route.zValue() for route in route_items)
    assert (item.pos().x(), item.pos().y()) == pytest.approx(requests[0].scene_position)
    assert item.scale() == pytest.approx(requests[0].pixel_scale)
    assert dialog.attribution.isVisible() and "OpenStreetMap" in dialog.attribution.text()
    QApplication.processEvents()
    visible = dialog.view.mapToScene(dialog.view.viewport().rect()).boundingRect()
    covered = item.mapRectToScene(item.boundingRect())
    assert covered.contains(visible)
    dialog.resize(1000, 750)
    QApplication.processEvents()
    assert len(requests) == 1
    dialog.map_button.click()
    wait_until(lambda: dialog.worker is None)
    assert dialog.map_item is item and "unavailable" in dialog.map_status.text()
    assert dialog.map_button.isEnabled()
    assert window.data is original and window.slider.value() == sample
    assert (window.axis_x.min(), window.axis_x.max()) == bounds
    window.set_ui_language(1)
    assert dialog.map_button.text() == "Kartenhintergrund laden"


def test_gps_map_close_cancels_and_late_result_cannot_replace_new_request(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.gps_button.click()
    dialog = window.gps_window
    assert isinstance(dialog, gps.GpsDialog)
    started, release = Event(), Event()
    requests: list[Event] = []

    def delayed(request: MapRequest, cancelled: Event) -> MapBackground:
        requests.append(cancelled)
        if len(requests) == 1:
            started.set()
            if not release.wait(6):
                raise MapError("test timeout")
        return background(request)

    monkeypatch.setattr(gps, "load_background", delayed)
    try:
        dialog.map_button.click()
        wait_until(started.is_set)
        dialog.close()
        assert requests[0].is_set()
        dialog.show()
        dialog.map_button.click()
        wait_until(lambda: dialog.worker is None)
        item = dialog.map_item
        assert item is not None
        release.set()
        QThreadPool.globalInstance().waitForDone()
        QApplication.processEvents()
        assert dialog.map_item is item
    finally:
        release.set()
        dialog.close()
        QThreadPool.globalInstance().waitForDone()
