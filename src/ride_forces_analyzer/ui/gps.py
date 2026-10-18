"""Offline spatial overview with independent Qt scene and no sensor timeline."""

from ride_forces_analyzer.i18n import tr
from .translation import bind

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.gps_overview import GpsOverview


class GpsView(QGraphicsView):
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
        dark = self.palette().base().color().lightness() < 128
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


def gps_dialog(overview: GpsOverview, title: str, parent: QWidget) -> QDialog:
    dialog = QDialog(parent)
    bind(dialog, tr("{0} — GPS overview", title), "windowTitle")
    dialog.resize(850, 650)
    layout = QVBoxLayout(dialog)
    label = bind(
        QLabel(),
        tr(
            "GPS reference • {0}/{1} usable positions • North up\nApproximate positions, not track geometry or force measurement. Missing fixes and timestamp gaps over 2 seconds are disconnected.\nBlue: source-order connections; green: first position; red: last position. No speed color scale or background map.",
            overview.count,
            overview.total,
        ),
    )
    label.setWordWrap(True)
    layout.addWidget(label)
    scene = QGraphicsScene(dialog)
    pen = QPen(QColor("#2563eb"), 2)
    pen.setCosmetic(True)
    for segment in overview.segments:
        for first, last in zip(segment, segment[1:]):
            scene.addLine(*first, *last, pen)
    points = overview.points
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
    view.style_route()
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    layout.addWidget(view)
    return dialog
