"""Viewport-only OSM requests, precise placement and cache behavior without network."""

from dataclasses import replace
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.request import Request

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QImageWriter
import pytest

from ride_forces_analyzer.gps import map_background as maps
from ride_forces_analyzer.gps.overview import GpsOverview
from ride_forces_analyzer.storage import map_tiles
from ride_forces_analyzer.storage.map_tiles import TileCache, TileEntry


def png(size: int = 256) -> bytes:
    image = QImage(size, size, QImage.Format.Format_RGB32)
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
    assert max(large.width, large.height) <= maps.MAX_IMAGE_SIZE
    high_density = maps.viewport_request(origin, bounds, (1700, 1300))
    assert high_density.zoom == request.zoom + 1
    assert high_density.pixel_scale == request.pixel_scale / 2
    assert high_density.width > request.width and high_density.height > request.height


def test_tiles_cache_then_revalidate_and_crop_exact_viewport(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)
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
    maps.load_background(request, Event(), cache_only=True)
    assert len(calls) == 1
    assert calls[0].full_url == "https://tile.openstreetmap.org/0/0/0.png"
    assert calls[0].data is None
    assert "Ride-Forces-Analyzer/" in str(calls[0].get_header("User-agent"))
    now[0] += 11
    with pytest.raises(maps.MapError, match="fresh in cache"):
        maps.load_background(request, Event(), cache_only=True)
    assert len(calls) == 1
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
    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)
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
    assert TileCache(export_directory / "map-cache.sqlite3").get(maps.TILE_URL, 0, 0, 0) is None


def test_missing_cache_headers_retain_tiles_for_seven_days(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)
    monkeypatch.setattr(maps, "time", lambda: 1000.0)

    def fetch(request: Request, *, timeout: float) -> Response:
        response = Response(png())
        response.headers = HTTPMessage()
        return response

    monkeypatch.setattr(maps, "urlopen", fetch)
    maps.load_background(maps.MapRequest(0, 0, 0, 256, 256, (0, 0)), Event())
    entry = TileCache(export_directory / "map-cache.sqlite3").get(maps.TILE_URL, 0, 0, 0)
    assert entry is not None and entry.expires == 1000 + 7 * 86400


@pytest.mark.parametrize("mode", ["broken-cache", "invalid-image", "no-store", "offline"])
def test_map_cache_failures_and_expired_responses(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)
    monkeypatch.setattr(maps, "time", lambda: 1000.0)
    path = export_directory / "map-cache.sqlite3"
    cache = TileCache(path)
    data = png()
    if mode == "broken-cache":
        path.mkdir()
    else:
        cache.put(
            maps.TILE_URL,
            0,
            0,
            0,
            TileEntry(b"invalid" if mode == "invalid-image" else data, 0, '"old"', ""),
        )
    calls: list[Request] = []

    def fetch(request: Request, *, timeout: float) -> Response:
        calls.append(request)
        if mode == "offline":
            raise URLError("offline")
        return Response(data, "no-store" if mode == "no-store" else "max-age=10")

    monkeypatch.setattr(maps, "urlopen", fetch)
    request = maps.MapRequest(0, 64, 64, 128, 128, (0, 0))
    if mode == "offline":
        with pytest.raises(maps.MapError):
            maps.load_background(request, Event())
        assert cache.get(maps.TILE_URL, 0, 0, 0) is not None
    else:
        result = maps.load_background(request, Event())
        assert not result.image.isNull()
        entry = cache.get(maps.TILE_URL, 0, 0, 0)
        if mode in ("broken-cache", "no-store"):
            assert entry is None
        else:
            assert entry is not None and entry.data == data
    assert len(calls) == 1
    if mode == "invalid-image":
        assert calls[0].get_header("If-none-match") is None


def test_missing_geographic_route_and_outside_world_viewport_remain_unavailable() -> None:
    assert maps.project_route(GpsOverview((((0, 0),),), 1, 1)) is None
    with pytest.raises(maps.MapError, match="viewport exceeds request limit"):
        maps.viewport_request((maps.WORLD_SIZE * 2, maps.WORLD_SIZE * 2), (0, 0, 1, 1), (100, 100))


@pytest.mark.parametrize(
    "map_request",
    [
        maps.MapRequest(20, 0, 0, 256, 256, (0, 0)),
        maps.MapRequest(0, 0, 0, 0, 256, (0, 0)),
        maps.MapRequest(0, 1024, 1024, 256, 256, (0, 0)),
        maps.MapRequest(4, 1, 1, 2048, 2048, (0, 0)),
    ],
)
def test_invalid_map_requests_are_rejected_before_loading(map_request: maps.MapRequest) -> None:
    with pytest.raises(maps.MapError, match="Invalid map request"):
        maps.load_background(map_request, Event())


def test_cache_control_and_expiry_fallbacks_are_respected(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)
    monkeypatch.setattr(maps, "time", lambda: 1000.0)
    expires = "Wed, 21 Oct 2026 07:28:00 GMT"
    cache = TileCache()
    for control, age, expected in (
        ("no-cache", "0", 1000.0),
        ("max-age=10", "invalid", datetime(2026, 10, 21, 7, 28, tzinfo=UTC).timestamp()),
    ):
        cache.clear()

        def fetch(request: Request, *, timeout: float) -> Response:
            response = Response(png(), control)
            response.headers["Age"] = age
            response.headers["Expires"] = expires
            return response

        monkeypatch.setattr(maps, "urlopen", fetch)
        maps.load_background(maps.MapRequest(0, 0, 0, 256, 256, (0, 0)), Event())
        entry = cache.get(maps.TILE_URL, 0, 0, 0)
        assert entry is not None and entry.expires == expected


def test_expired_tile_without_etag_uses_last_modified(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)
    cache = TileCache()
    cache.put(maps.TILE_URL, 0, 0, 0, TileEntry(png(), 0, "", "Wed, 21 Oct 2026 07:28:00 GMT"))

    def fetch(request: Request, *, timeout: float) -> Response:
        assert request.get_header("If-none-match") is None
        assert request.get_header("If-modified-since") == "Wed, 21 Oct 2026 07:28:00 GMT"
        return Response(png())

    monkeypatch.setattr(maps, "urlopen", fetch)
    assert not maps.load_background(
        maps.MapRequest(0, 0, 0, 256, 256, (0, 0)),
        Event(),
    ).image.isNull()


@pytest.mark.parametrize("mode", ["wrong-size", "http-error", "cancel-during-load", "deadline"])
def test_tile_failures_and_late_cancellation_never_publish_a_background(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    from unittest.mock import Mock

    monkeypatch.setattr(map_tiles, "data_directory", lambda: export_directory)
    cancelled = Event()
    calls: list[Request] = []

    def fetch(request: Request, *, timeout: float) -> Response:
        calls.append(request)
        if mode == "http-error":
            raise HTTPError(request.full_url, 404, "Not found", HTTPMessage(), None)
        if mode == "cancel-during-load":
            cancelled.set()
        return Response(png(128 if mode == "wrong-size" else 256))

    monkeypatch.setattr(maps, "urlopen", fetch)
    if mode == "deadline":
        monkeypatch.setattr(maps, "monotonic", Mock(side_effect=[0.0, 21.0]))
    with pytest.raises(
        maps.MapError,
        match="Invalid map tile|Map server unavailable|Map request stopped",
    ):
        maps.load_background(maps.MapRequest(0, 0, 0, 256, 256, (0, 0)), cancelled)
    assert len(calls) == (0 if mode == "deadline" else 1)
