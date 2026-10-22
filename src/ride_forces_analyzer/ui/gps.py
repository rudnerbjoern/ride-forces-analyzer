"""Independent GPS scene with an explicit optional map request, never a sensor timeline.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap

from ride_forces_analyzer.i18n import tr
from .translation import bind

from threading import Event

from PySide6.QtCore import QEvent, Qt, QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPen, QResizeEvent, QCloseEvent, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.gps_overview import GpsOverview
from ride_forces_analyzer.map_background import (
    MapBackground,
    MapError,
    MapRequest,
    load_background,
    project_route,
    viewport_request,
)


class MapSignals(QObject):
    completed = Signal(int, object)
    failed = Signal(int)


class MapWorker(QRunnable):
    def __init__(self, request: MapRequest, revision: int, cancelled: Event) -> None:
        super().__init__()
        self.request, self.revision, self.cancelled = request, revision, cancelled
        self.signals = MapSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = load_background(self.request, self.cancelled)
        except Exception:
            self.signals.failed.emit(self.revision)
        else:
            self.signals.completed.emit(self.revision, result)


class GpsView(QGraphicsView):
    map_visible = False

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.LanguageChange,
            QEvent.Type.LocaleChange,
        ):
            self.style_route()

    def style_route(self) -> None:
        scene = self.scene()
        dark = self.palette().base().color().lightness() < 128 and not self.map_visible
        colors = ("#4e9bff", "#35f58a", "#ff687a") if dark else ("#2563eb", "#08783b", "#bc2339")
        for item in scene.items():
            role = item.data(0)
            color = QColor(colors[1 if role == "start" else 2 if role == "end" else 0])
            if isinstance(item, (QGraphicsLineItem, QGraphicsEllipseItem)):
                pen = item.pen()
                pen.setColor(color)
                item.setPen(pen)
                if role in ("start", "end") and isinstance(item, QGraphicsEllipseItem):
                    item.setBrush(color)
            elif isinstance(item, QGraphicsSimpleTextItem):
                item.setText(tr("Start" if role == "start" else "End"))
                item.setBrush(color)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class GpsDialog(QDialog):
    view: GpsView
    map_button: QPushButton
    map_status: QLabel
    attribution: QLabel

    def __init__(self, overview: GpsOverview, title: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.revision = 0
        self.stopped = False
        self.cancelled = Event()
        self.worker: MapWorker | None = None
        self.route = project_route(overview)
        self.map_item: QGraphicsItem | None = None
        _populate_dialog(self, overview, title)

    @Slot()
    def load_map(self) -> None:
        if self.stopped or self.worker is not None or self.route is None:
            return
        bounds = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        viewport = self.view.viewport()
        density = viewport.devicePixelRatioF()
        try:
            request = viewport_request(
                self.route.origin,
                (bounds.x(), bounds.y(), bounds.width(), bounds.height()),
                (round(viewport.width() * density), round(viewport.height() * density)),
            )
        except MapError:
            self.map_failed(self.revision)
            return
        self.revision += 1
        self.cancelled = Event()
        worker = MapWorker(request, self.revision, self.cancelled)
        worker.signals.completed.connect(self.map_ready)
        worker.signals.failed.connect(self.map_failed)
        self.worker = worker
        self.map_button.setEnabled(False)
        bind(self.map_status, tr("Loading map…"))
        QThreadPool.globalInstance().start(worker)

    @Slot(int, object)
    def map_ready(self, revision: int, result: object) -> None:
        if self.stopped or revision != self.revision or not isinstance(result, MapBackground):
            return
        self.worker = None
        self.map_button.setEnabled(True)
        scene = self.view.scene()
        if self.map_item is not None:
            scene.removeItem(self.map_item)
        item = scene.addPixmap(QPixmap.fromImage(result.image))
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        item.setPos(*result.request.scene_position)
        item.setScale(result.request.pixel_scale)
        item.setZValue(-1)
        self.map_item = item
        self.view.map_visible = True
        self.view.style_route()
        self.attribution.show()
        bind(self.map_status, tr("Map loaded. Resize and load again to update the visible area."))

    @Slot(int)
    def map_failed(self, revision: int) -> None:
        if self.stopped or revision != self.revision:
            return
        self.worker = None
        self.map_button.setEnabled(True)
        bind(self.map_status, tr("Map unavailable. The GPS track remains usable."))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stopped = True
        self.revision += 1
        self.cancelled.set()
        self.worker = None
        self.map_button.setEnabled(self.route is not None)
        super().closeEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        self.stopped = False
        super().showEvent(event)


def _populate_dialog(dialog: GpsDialog, overview: GpsOverview, title: str) -> None:
    bind(dialog, tr("{0} — GPS overview", title), "windowTitle")
    dialog.resize(850, 650)
    layout = QVBoxLayout(dialog)
    label = bind(
        QLabel(),
        tr(
            "GPS reference • {0}/{1} usable positions • North up\nApproximate positions, not track geometry or force measurement. Missing fixes and timestamp gaps over 2 seconds are disconnected.\nBlue: source-order connections; green: first position; red: last position. No speed color scale.",
            overview.count,
            overview.total,
        ),
    )
    label.setWordWrap(True)
    layout.addWidget(label)
    scene = QGraphicsScene(dialog)
    pen = QPen(QColor("#2563eb"), 2)
    pen.setCosmetic(True)
    route_pen = QPen(pen)
    route_pen.setWidth(4)
    segments = dialog.route.segments if dialog.route is not None else overview.segments
    for segment in segments:
        for first, last in zip(segment, segment[1:]):
            scene.addLine(*first, *last, route_pen)
    points = tuple(point for segment in segments for point in segment)
    extent = max(
        max(x for x, _ in points) - min(x for x, _ in points),
        max(y for _, y in points) - min(y for _, y in points),
        10.0,
    )
    radius = extent / 150
    for x, y in points:
        scene.addEllipse(x - radius, y - radius, 2 * radius, 2 * radius, pen)
    for point, color, role, text in (
        (points[0], "#16a34a", "start", tr("Start")),
        (points[-1], "#dc2626", "end", tr("End")),
    ):
        x, y = point
        marker = scene.addEllipse(
            x - 2 * radius,
            y - 2 * radius,
            4 * radius,
            4 * radius,
            QPen(QColor(color)),
            QColor(color),
        )
        marker.setData(0, role)
        item = scene.addSimpleText(text)
        item.setData(0, role)
        item.setBrush(QColor(color))
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        item.setPos(x + 3 * radius, y + 3 * radius)
    bounds = scene.itemsBoundingRect()
    scene.setSceneRect(
        bounds.adjusted(-extent * 0.05, -extent * 0.05, extent * 0.05, extent * 0.05),
    )
    view = GpsView(scene, dialog)
    dialog.view = view
    view.style_route()
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    layout.addWidget(view)
    dialog.map_button = bind(QPushButton(), tr("Load map background"))
    bind(
        dialog.map_button,
        tr(
            "Loads the visible area from OpenStreetMap. Your IP address and the map area are sent; the GPS track stays local.",
        ),
        "toolTip",
    )
    dialog.map_button.setEnabled(dialog.route is not None)
    dialog.map_button.clicked.connect(dialog.load_map)
    layout.addWidget(dialog.map_button)
    dialog.map_status = QLabel()
    dialog.map_status.setWordWrap(True)
    dialog.map_status.setMinimumHeight(2 * dialog.map_status.fontMetrics().height())
    if dialog.route is None:
        bind(dialog.map_status, tr("Map unavailable for these coordinates."))
    layout.addWidget(dialog.map_status)
    dialog.attribution = QLabel(
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    )
    dialog.attribution.setOpenExternalLinks(True)
    policy = dialog.attribution.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    dialog.attribution.setSizePolicy(policy)
    dialog.attribution.hide()
    layout.addWidget(dialog.attribution)


def gps_dialog(overview: GpsOverview, title: str, parent: QWidget) -> GpsDialog:
    return GpsDialog(overview, title, parent)
