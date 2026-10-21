"""Project identity and license information.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer import __version__
from ride_forces_analyzer.i18n import tr

from .translation import bind
from .updates import UpdateController


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget, updates: UpdateController) -> None:
        super().__init__(parent)
        self.setObjectName("aboutDialog")
        bind(self, tr("About Ride Forces Analyzer"), "windowTitle")
        self.resize(600, 520)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        content = QVBoxLayout(body)
        for text in (
            tr("Ride Forces Analyzer · Version {0}", __version__),
            tr(
                "Explore ride recordings and export G-force overlays for your videos. Processing stays offline and original recordings remain unchanged.",
            ),
            tr(
                "Record your rides with the Ride Forces app for iPhone or Apple Watch, then export them as .forces or .zforces files.",
            ),
            tr(
                "Independent project: not affiliated with, endorsed by or sponsored by the Ride Forces app or its developer.",
            ),
            "Copyright © 2026 Björn Rudner",
            tr(
                "Code: GNU GPL version 3 or later. Supplied test recordings and documentation images: CC BY-SA 4.0. Third-party components retain their own licenses. Provided without warranty.",
            ),
        ):
            label = bind(QLabel(), text)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            content.addWidget(label)
        links = QLabel(
            '<a href="https://github.com/rudnerbjoern/ride-forces-analyzer">GitHub</a> · '
            '<a href="https://github.com/rudnerbjoern/ride-forces-analyzer/blob/main/LICENSE">GPL</a> · '
            '<a href="https://rideforces.com/">Ride Forces</a>',
        )
        links.setWordWrap(True)
        links.setOpenExternalLinks(True)
        content.addWidget(links)
        notices = bind(
            QLabel(),
            tr(
                '<a href="{0}">Third-party notices</a>',
                "https://github.com/rudnerbjoern/ride-forces-analyzer/blob/main/THIRD_PARTY_NOTICES.md",
            ),
        )
        notices.setOpenExternalLinks(True)
        content.addWidget(notices)
        self.automatic_updates = bind(
            QCheckBox(),
            tr("Check for updates at startup (once per day)"),
        )
        self.automatic_updates.setChecked(updates.preferences.automatic_updates())
        self.automatic_updates.toggled.connect(updates.preferences.remember_automatic_updates)
        content.addWidget(self.automatic_updates)
        privacy = bind(
            QLabel(),
            tr("Optional GitHub connection. No recordings, GPS data or file paths are sent."),
        )
        privacy.setWordWrap(True)
        content.addWidget(privacy)
        self.check_updates = bind(QPushButton(), tr("Check for updates…"))
        self.check_updates.setEnabled(updates.worker is None)
        self.check_updates.clicked.connect(lambda: updates.check(manual=True))
        updates.busy_changed.connect(self.check_updates.setDisabled)
        content.addWidget(self.check_updates)
        self.update_status = QLabel()
        self.update_status.setTextFormat(Qt.TextFormat.PlainText)
        self.update_status.setWordWrap(True)
        updates.status_changed.connect(self._update_status)
        content.addWidget(self.update_status)
        content.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        close = bind(QPushButton(), tr("Close"))
        close.clicked.connect(self.close)
        layout.addWidget(close)

    def _update_status(self, message: object) -> None:
        if isinstance(message, str):
            bind(self.update_status, message)
