"""Offline spatial overview with independent Qt scene and no sensor timeline."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.gps_overview import GpsOverview


class GpsView(QGraphicsView):
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def gps_dialog(overview: GpsOverview, title: str, parent: QWidget) -> QDialog:
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"{title} — GPS overview")
    dialog.resize(850, 650)
    layout = QVBoxLayout(dialog)
    label = QLabel(
        f"GPS reference • {overview.count}/{overview.total} usable positions • North up\n"
        "Approximate positions, not track geometry or force measurement. "
        "Missing fixes and timestamp gaps over 2 seconds are disconnected.\n"
        "Blue: source-order connections; green: first position; red: last position. "
        "No speed color scale or background map.",
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
    for point, color, text in ((points[0], "#16a34a", "Start"), (points[-1], "#dc2626", "End")):
        x, y = point
        scene.addEllipse(
            x - 2 * radius,
            y - 2 * radius,
            4 * radius,
            4 * radius,
            QPen(QColor(color)),
            QColor(color),
        )
        item = scene.addSimpleText(text)
        item.setBrush(QColor(color))
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        item.setPos(x + 3 * radius, y + 3 * radius)
    bounds = scene.itemsBoundingRect()
    scene.setSceneRect(
        bounds.adjusted(-extent * 0.05, -extent * 0.05, extent * 0.05, extent * 0.05),
    )
    view = GpsView(scene, dialog)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    layout.addWidget(view)
    return dialog
