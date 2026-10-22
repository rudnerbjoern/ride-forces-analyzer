"""Opt-in OSM viewport tiles, Web Mercator placement and HTTP-aware local cache.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

# cspell:words ARGB

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from email.message import Message
from math import asinh, ceil, floor, isfinite, log2, pi, radians, tan
import re
from threading import Event
from time import monotonic, time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from . import __version__
from .gps_overview import GpsOverview
from .storage.map_tiles import TileCache, TileEntry

TILE_SIZE = 256
WORLD_SIZE = 2 * pi * 6378137
MAX_LATITUDE = 85.0511287798066
MAX_TILE_BYTES = 1024 * 1024
MAX_TILES = 64
MAX_IMAGE_SIZE = 2048
CACHE_SECONDS = 7 * 86400
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = (
    f"Ride-Forces-Analyzer/{__version__} (+https://github.com/rudnerbjoern/ride-forces-analyzer)"
)


class MapError(Exception):
    """A requested map cannot be prepared; the route remains usable."""


def project(latitude: float, longitude: float) -> tuple[float, float]:
    """Return north-up Web Mercator coordinates with scene y increasing southward."""
    if not -MAX_LATITUDE <= latitude <= MAX_LATITUDE or not -180 <= longitude <= 180:
        raise MapError("Position outside Web Mercator coverage")
    return 6378137 * radians(longitude), -6378137 * asinh(tan(radians(latitude)))


@dataclass(frozen=True, slots=True)
class MapRoute:
    origin: tuple[float, float]
    segments: tuple[tuple[tuple[float, float], ...], ...]


def project_route(overview: GpsOverview) -> MapRoute | None:
    """Preserve source gaps/order; polar coordinates keep the original offline view."""
    if not overview.geographic_segments:
        return None
    try:
        origin = project(*overview.geographic_segments[0][0])
        segments = tuple(
            tuple((x - origin[0], y - origin[1]) for x, y in (project(*point) for point in segment))
            for segment in overview.geographic_segments
        )
    except MapError:
        return None
    return MapRoute(origin, segments)


@dataclass(frozen=True, slots=True)
class MapRequest:
    """Only visible pixels and their tile coordinates; never a GPS track payload."""

    zoom: int
    left: int
    top: int
    width: int
    height: int
    origin: tuple[float, float]

    @property
    def pixel_scale(self) -> float:
        return WORLD_SIZE / (TILE_SIZE * (1 << self.zoom))

    @property
    def scene_position(self) -> tuple[float, float]:
        return (
            self.left * self.pixel_scale - WORLD_SIZE / 2 - self.origin[0],
            self.top * self.pixel_scale - WORLD_SIZE / 2 - self.origin[1],
        )

    @property
    def tiles(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (x, y)
            for y in range(
                max(0, self.top // TILE_SIZE),
                min(2**self.zoom, (self.top + self.height - 1) // TILE_SIZE + 1),
            )
            for x in range(
                max(0, self.left // TILE_SIZE),
                min(2**self.zoom, (self.left + self.width - 1) // TILE_SIZE + 1),
            )
        )


def viewport_request(
    origin: tuple[float, float],
    bounds: tuple[float, float, float, float],
    size: tuple[int, int],
) -> MapRequest:
    """Choose one fitting zoom and request only tiles intersecting the visible area."""
    x, y, width, height = bounds
    if not all(isfinite(value) for value in (*origin, *bounds)) or min(width, height, *size) <= 0:
        raise MapError("Invalid map viewport")
    density = min(min(size[0], MAX_IMAGE_SIZE) / width, min(size[1], MAX_IMAGE_SIZE) / height)
    zoom = max(0, min(19, floor(log2(density * WORLD_SIZE / TILE_SIZE))))
    for level in range(zoom, -1, -1):
        scale = WORLD_SIZE / (TILE_SIZE * (1 << level))
        left = floor((origin[0] + x + WORLD_SIZE / 2) / scale)
        top = floor((origin[1] + y + WORLD_SIZE / 2) / scale)
        request = MapRequest(
            level,
            left,
            top,
            ceil((origin[0] + x + width + WORLD_SIZE / 2) / scale) - left,
            ceil((origin[1] + y + height + WORLD_SIZE / 2) / scale) - top,
            origin,
        )
        if (
            request.tiles
            and len(request.tiles) <= MAX_TILES
            and max(request.width, request.height) <= MAX_IMAGE_SIZE
        ):
            return request
    raise MapError("Map viewport exceeds request limit")


def _expiry(headers: Message[str, str], now: float) -> float:
    control = headers.get("Cache-Control", "").lower()
    if "no-cache" in control:
        return now
    match = re.search(r"(?:^|,)\s*max-age\s*=\s*(\d+)", control)
    if match:
        try:
            return now + max(0, int(match[1]) - int(headers.get("Age", "0")))
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(headers["Expires"]).timestamp()
    except KeyError, TypeError, ValueError, OverflowError:
        return now + CACHE_SECONDS


def _image(data: bytes) -> QImage:
    if len(data) > MAX_TILE_BYTES or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise MapError("Invalid map tile")
    image = QImage.fromData(data)
    if (
        len(data) > MAX_TILE_BYTES
        or image.isNull()
        or (image.width(), image.height()) != (256, 256)
    ):
        raise MapError("Invalid map tile")
    return image


def _tile(zoom: int, x: int, y: int, cache: TileCache) -> QImage:
    entry = cache.get(TILE_URL, zoom, x, y)
    cached: QImage | None = None
    if entry is not None:
        try:
            cached = _image(entry.data)
            if isfinite(entry.expires) and entry.expires > time():
                return cached
        except MapError:
            cache.delete(TILE_URL, zoom, x, y)
            entry = None
    headers = {"User-Agent": USER_AGENT, "Accept": "image/png"}
    if entry is not None:
        if entry.etag:
            headers["If-None-Match"] = entry.etag
        if entry.modified:
            headers["If-Modified-Since"] = entry.modified
    try:
        with urlopen(
            Request(TILE_URL.format(z=zoom, x=x, y=y), headers=headers),
            timeout=5,
        ) as response:
            data = bytes(response.read(MAX_TILE_BYTES + 1))
            image = _image(data)
            response_headers = response.headers
            entry = None
    except HTTPError as error:
        if error.code != 304 or cached is None or entry is None:
            raise MapError("Map server unavailable") from error
        image, data, response_headers = cached, entry.data, error.headers
    if "no-store" in response_headers.get("Cache-Control", "").lower():
        cache.delete(TILE_URL, zoom, x, y)
    else:
        cache.put(
            TILE_URL,
            zoom,
            x,
            y,
            TileEntry(
                data,
                _expiry(response_headers, time()),
                response_headers.get("ETag", entry.etag if entry is not None else ""),
                response_headers.get("Last-Modified", entry.modified if entry is not None else ""),
            ),
        )
    return image


@dataclass(frozen=True, slots=True)
class MapBackground:
    request: MapRequest
    image: QImage


def load_background(request: MapRequest, cancelled: Event) -> MapBackground:
    """Load a single viewport with bounded sequential HTTPS, cache and cancellation."""
    if (
        not 0 <= request.zoom <= 19
        or not 0 < request.width <= MAX_IMAGE_SIZE
        or not 0 < request.height <= MAX_IMAGE_SIZE
        or not request.tiles
        or len(request.tiles) > MAX_TILES
    ):
        raise MapError("Invalid map request")
    deadline = monotonic() + 20
    tiles: list[tuple[int, int, QImage]] = []
    cache = TileCache()
    try:
        for x, y in request.tiles:
            if cancelled.is_set() or monotonic() >= deadline:
                raise MapError("Map request stopped")
            tiles.append((x, y, _tile(request.zoom, x, y, cache)))
    except (OSError, URLError, ValueError) as error:
        raise MapError("Map could not be loaded") from error
    if cancelled.is_set():
        raise MapError("Map request stopped")
    image = QImage(request.width, request.height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        for x, y, tile in tiles:
            painter.drawImage(x * TILE_SIZE - request.left, y * TILE_SIZE - request.top, tile)
    finally:
        painter.end()
    return MapBackground(request, image)
