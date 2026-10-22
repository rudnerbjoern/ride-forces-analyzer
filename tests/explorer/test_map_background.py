"""Viewport-only OSM requests, precise placement and cache behavior without network."""

from dataclasses import replace
from http.client import HTTPMessage
from io import BytesIO
import json
from pathlib import Path
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.request import Request

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QImageWriter
import pytest

from ride_forces_analyzer import map_background as maps
from ride_forces_analyzer.gps_overview import GpsOverview


def png() -> bytes:
    image = QImage(256, 256, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.cyan)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert QImageWriter(buffer, b"png").write(image)
    return bytes(buffer.data().data())


class Response(BytesIO):
    def __init__(self, data: bytes, control: str = "max-age=10") -> None:
        super().__init__(data)
        self.headers = HTTPMessage()
        self.headers["Cache-Control"] = control
        self.headers["ETag"] = '"tile-1"'
        self.headers["Last-Modified"] = "Wed, 21 Oct 2026 07:28:00 GMT"


def test_map_projection_matches_tile_grid_without_bridging_source_gaps() -> None:
    assert maps.project(0, 0) == (0, 0)
    east, north = maps.project(45, 45)
    assert east == pytest.approx(maps.WORLD_SIZE / 8)
    assert north < 0
    overview = GpsOverview(
        (((0, 0), (1, -1)), ((2, -2),)),
        3,
        4,
        (((0, 0), (0.001, 0.001)), ((0.002, 0.002),)),
    )
    route = maps.project_route(overview)
    assert route is not None
    assert [len(segment) for segment in route.segments] == [2, 1]
    assert route.segments[0][0] == (0, 0)
    assert route.segments[1][0] == maps.project(0.002, 0.002)
    assert maps.project_route(replace(overview, geographic_segments=(((90, 0),),))) is None


def test_viewport_request_is_bounded_and_georeferenced() -> None:
    origin = maps.project(48, 7)
    bounds = (-200.0, -150.0, 800.0, 600.0)
    request = maps.viewport_request(origin, bounds, (850, 650))
    assert 0 <= request.zoom <= 19 and 1 <= len(request.tiles) <= maps.MAX_TILES
    assert request.width <= 850 + 2 and request.height <= 650 + 2
    x, y = request.scene_position
    assert x <= bounds[0] < x + request.pixel_scale
    assert y <= bounds[1] < y + request.pixel_scale
    assert x + request.width * request.pixel_scale >= bounds[0] + bounds[2]
    assert y + request.height * request.pixel_scale >= bounds[1] + bounds[3]
    for tile_x, tile_y in request.tiles:
        assert tile_x * 256 < request.left + request.width
        assert (tile_x + 1) * 256 > request.left
        assert tile_y * 256 < request.top + request.height
        assert (tile_y + 1) * 256 > request.top
    with pytest.raises(maps.MapError):
        maps.viewport_request(origin, (0, 0, 0, 1), (850, 650))
    large = maps.viewport_request(origin, (-600, -600, 1200, 1200), (3840, 2160))
    assert 1 <= len(large.tiles) <= maps.MAX_TILES


def test_tiles_cache_then_revalidate_and_crop_exact_viewport(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maps, "data_directory", lambda: export_directory)
    now = [1000.0]
    monkeypatch.setattr(maps, "time", lambda: now[0])
    calls: list[Request] = []
    data = png()

    def fetch(request: Request, *, timeout: float) -> Response:
        assert timeout == 5
        calls.append(request)
        if len(calls) > 1:
            raise HTTPError(request.full_url, 304, "Not modified", Response(data).headers, None)
        return Response(data)

    monkeypatch.setattr(maps, "urlopen", fetch)
    request = maps.MapRequest(0, 64, 64, 128, 128, (0, 0))
    first = maps.load_background(request, Event())
    assert (first.image.width(), first.image.height()) == (128, 128)
    assert first.image.pixelColor(0, 0) == QImage.fromData(data).pixelColor(64, 64)
    maps.load_background(request, Event())
    assert len(calls) == 1
    assert calls[0].full_url == "https://tile.openstreetmap.org/0/0/0.png"
    assert calls[0].data is None
    assert "Ride-Forces-Analyzer/" in str(calls[0].get_header("User-agent"))
    now[0] += 11
    maps.load_background(request, Event())
    assert len(calls) == 2
    assert calls[1].get_header("If-none-match") == '"tile-1"'
    assert calls[1].get_header("If-modified-since")
    maps.load_background(request, Event())
    assert len(calls) == 2


@pytest.mark.parametrize("mode", ["no-store", "invalid", "offline", "cancelled"])
def test_unavailable_tiles_and_cancellation_keep_cache_and_requests_honest(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setattr(maps, "data_directory", lambda: export_directory)
    calls: list[Request] = []

    def fetch(request: Request, *, timeout: float) -> Response:
        calls.append(request)
        if mode == "offline":
            raise URLError("offline")
        return Response(b"invalid" if mode == "invalid" else png(), "no-store")

    monkeypatch.setattr(maps, "urlopen", fetch)
    cancelled = Event()
    if mode == "cancelled":
        cancelled.set()
    request = maps.MapRequest(0, 64, 64, 128, 128, (0, 0))
    if mode == "no-store":
        maps.load_background(request, cancelled)
        maps.load_background(request, cancelled)
        assert len(calls) == 2
    else:
        with pytest.raises(maps.MapError):
            maps.load_background(request, cancelled)
    assert len(calls) == (0 if mode == "cancelled" else 2 if mode == "no-store" else 1)
    assert not list(export_directory.rglob("*.png"))


def test_missing_cache_headers_retain_tiles_for_seven_days(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maps, "data_directory", lambda: export_directory)
    monkeypatch.setattr(maps, "time", lambda: 1000.0)

    def fetch(request: Request, *, timeout: float) -> Response:
        response = Response(png())
        response.headers = HTTPMessage()
        return response

    monkeypatch.setattr(maps, "urlopen", fetch)
    maps.load_background(maps.MapRequest(0, 0, 0, 256, 256, (0, 0)), Event())
    metadata = json.loads(next(export_directory.rglob("*.json")).read_text(encoding="utf-8"))
    assert metadata["expires"] == 1000 + 7 * 86400
