"""Qt preview image conversion and aspect-preserving display.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr

# cspell:words pixmap Deutsch


from PySide6.QtCore import (
    Qt,
)
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
)
from PIL import Image


def preview_pixmap(image: Image.Image) -> QPixmap:
    """Copy an RGB preview image into a Qt pixmap owned by the GUI thread.

    Args:
        image: Prepared RGB preview image to copy without changing its pixels.

    Returns:
        A Qt pixmap with storage independent of the source image bytes.
    """
    raw = image.tobytes()
    return QPixmap.fromImage(
        QImage(raw, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy(),
    )


class PreviewView(QLabel):
    """Display an aspect-preserving preview image inside the available dialog space.

    Attributes:
        source: Retained input identity or image; its original representation remains
            owned.
    """

    def __init__(self) -> None:
        """Initialize preview view and its owned state.

        Returns:
            None.
        """
        super().__init__(tr("Preparing preview…"))
        self.source = QPixmap()
        self.setMinimumSize(440, 248)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def show_image(self, image: Image.Image) -> None:
        """Display a prepared preview image without changing its source pixels.

        Args:
            image: Raster image to inspect or draw into.

        Returns:
            None.
        """
        self.source = preview_pixmap(image)
        self._fit()

    def _fit(self) -> None:
        if not self.source.isNull():
            self.setPixmap(
                self.source.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update view geometry after a Qt resize event.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        super().resizeEvent(event)
        self._fit()
