"""Explicit map requests stay independent of recordings and ignore stale workers."""

# cspell:words Kartenhintergrund laden Pixmap

from pathlib import Path
from threading import Event

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QPushButton
import pytest

from ride_forces_analyzer.gps.map_background import MapBackground, MapError, MapRequest
from ride_forces_analyzer.ui.dialogs import gps
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
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

    QApplication.processEvents()
    wait_until(lambda: dialog.worker is None)
    monkeypatch.setattr(gps, "load_background", load)
    QApplication.processEvents()
    assert not requests and dialog.map_item is None
    assert not dialog.attribution.isVisible()
    original = window.data
    sample = window.navigation.slider.value()
    bounds = (window.plot.axis_x.min(), window.plot.axis_x.max())
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
    close = next(button for button in dialog.findChildren(QPushButton) if button.text() == "Close")
    layout = dialog.layout()
    assert layout is not None
    margins = layout.contentsMargins()
    assert close.geometry().right() == dialog.width() - margins.right() - 1
    assert close.geometry().bottom() == dialog.height() - margins.bottom() - 1
    assert close.geometry().left() > dialog.map_button.geometry().right()
    assert close.geometry().bottom() == dialog.map_button.geometry().bottom()
    assert len(requests) == 1
    dialog.map_button.click()
    wait_until(lambda: dialog.worker is None)
    assert dialog.map_item is item and "unavailable" in dialog.map_status.text()
    assert dialog.map_button.isEnabled()
    assert window.data is original and window.navigation.slider.value() == sample
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == bounds
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

    QApplication.processEvents()
    wait_until(lambda: dialog.worker is None)
    monkeypatch.setattr(gps, "load_background", delayed)
    try:
        dialog.map_button.click()
        wait_until(started.is_set)
        close = next(
            button for button in dialog.findChildren(QPushButton) if button.text() == "Close"
        )
        close.click()
        assert not dialog.isVisible()
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


def test_new_gps_dialog_restores_persistent_cached_map_without_network(
    explorer_window: ExplorerWindow,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from time import time

    from ride_forces_analyzer.gps import map_background as maps
    from ride_forces_analyzer.gps.overview import GpsOverview
    from ride_forces_analyzer.storage import map_tiles
    from ride_forces_analyzer.storage.map_tiles import TileCache, TileEntry
    from tests.explorer.test_map_background import png

    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)

    def no_network(*args: object, **kwargs: object) -> None:
        pytest.fail("Opening GPS must never access the network")

    monkeypatch.setattr(maps, "urlopen", no_network)
    overview = GpsOverview((((0, 0), (100, 100)),), 2, 2, (((48, 7), (48.001, 7.001)),))
    requests: list[MapRequest] = []

    def cached(request: MapRequest, cancelled: Event, *, cache_only: bool = False) -> MapBackground:
        assert cache_only
        requests.append(request)
        return maps.load_background(request, cancelled, cache_only=True)

    monkeypatch.setattr(gps, "load_background", cached)
    first = gps.gps_dialog(overview, "Cached route", explorer_window)
    first.show()
    wait_until(lambda: bool(requests) and first.worker is None)
    assert first.map_item is None and first.map_button.isEnabled()
    request = requests[-1]
    first.close()
    first.deleteLater()
    cache = TileCache()
    for x, y in request.tiles:
        cache.put(maps.TILE_URL, request.zoom, x, y, TileEntry(png(), time() + 3600, "", ""))
    # A new dialog/controller reads the database without any retained map image.
    reopened = gps.gps_dialog(overview, "Cached route", explorer_window)
    try:
        reopened.show()
        wait_until(lambda: len(requests) == 2 and reopened.worker is None)
        assert reopened.map_item is not None
        assert reopened.attribution.isVisible()
        assert reopened.view.map_visible
    finally:
        reopened.close()
