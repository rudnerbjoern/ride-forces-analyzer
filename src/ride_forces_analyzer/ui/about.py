"""Project identity and license information.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap pixmap

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer import __version__
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.diagnostics import collect_diagnostics

from .translation import bind
from .chrome import app_icon
from .updates import UpdateController


class _DiagnosticSignals(QObject):
    completed = Signal(str)


class _DiagnosticWorker(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = _DiagnosticSignals()

    @Slot()
    def run(self) -> None:
        try:
            report = collect_diagnostics()
        except Exception:
            report = "Diagnostics: Collection failed"
        self.signals.completed.emit(report)


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget, updates: UpdateController) -> None:
        super().__init__(parent)
        self.setObjectName("aboutDialog")
        bind(self, tr("About Ride Forces Analyzer"), "windowTitle")
        self.resize(660, 520)
        self.setStyleSheet(
            "QLabel#aboutTitle { font-size: 22px; font-weight: 600; }"
            "QLabel#aboutFinePrint { font-size: 8pt; }",
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 0, 8, 0)
        content.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(64, 64))
        icon.setFixedSize(64, 64)
        header.addWidget(icon)
        identity = QVBoxLayout()
        identity.setSpacing(4)
        title = QLabel("Ride Forces Analyzer")
        title.setObjectName("aboutTitle")
        identity.addWidget(title)
        identity.addWidget(bind(QLabel(), tr("Version {0}", __version__)))
        header.addLayout(identity, 1)
        content.addLayout(header)
        summary = bind(
            QLabel(),
            tr(
                "Explore ride forces and create video overlays. Offline, with your original recordings unchanged.",
            ),
        )
        summary.setWordWrap(True)
        content.addWidget(summary)
        links = bind(
            QLabel(),
            tr(
                '<a href="{0}">GitHub</a> · <a href="{1}">Ride Forces app</a> · <a href="{2}">License</a> · <a href="{3}">Third-party notices</a>',
                "https://github.com/rudnerbjoern/ride-forces-analyzer",
                "https://rideforces.com/",
                "https://github.com/rudnerbjoern/ride-forces-analyzer/blob/main/LICENSE",
                "https://github.com/rudnerbjoern/ride-forces-analyzer/blob/main/THIRD_PARTY_NOTICES.md",
            ),
        )
        links.setWordWrap(True)
        links.setOpenExternalLinks(True)
        content.addWidget(links)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        content.addWidget(separator)
        heading = bind(QLabel(), tr("Updates"))
        heading.setObjectName("SectionTitle")
        content.addWidget(heading)
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
        self.check_updates = bind(QPushButton(), tr("Check for updates…"))
        self.check_updates.setEnabled(updates.worker is None)
        self.check_updates.clicked.connect(lambda: updates.check(manual=True))
        updates.busy_changed.connect(self.check_updates.setDisabled)
        update_actions = QHBoxLayout()
        update_actions.addWidget(self.check_updates)
        update_actions.addStretch()
        content.addLayout(update_actions)
        self.update_status = QLabel()
        self.update_status.setTextFormat(Qt.TextFormat.PlainText)
        self.update_status.setWordWrap(True)
        self.update_status.hide()
        updates.status_changed.connect(self._update_status)
        content.addWidget(self.update_status)
        privacy.setObjectName("aboutFinePrint")
        content.addWidget(privacy)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        content.addWidget(separator)
        for text in (
            "Copyright © 2026 Björn Rudner",
            tr(
                "Independent project: not affiliated with, endorsed by or sponsored by the Ride Forces app or its developer.",
            ),
            tr(
                "Code: GNU GPL version 3 or later. Supplied test recordings and documentation images: CC BY-SA 4.0. Third-party components retain their own licenses. Provided without warranty.",
            ),
        ):
            label = bind(QLabel(), text)
            label.setObjectName("aboutFinePrint")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            content.addWidget(label)
        self.diagnostic_worker: _DiagnosticWorker | None = None
        self.copy_diagnostics = bind(QPushButton(), tr("Copy diagnostic information"))
        self.copy_diagnostics.clicked.connect(self._copy_diagnostics)
        self.copy_reset = QTimer(self)
        self.copy_reset.setSingleShot(True)
        self.copy_reset.timeout.connect(self._reset_copy_label)
        content.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        close = bind(QPushButton(), tr("Close"))
        close.clicked.connect(self.close)
        actions = QHBoxLayout()
        actions.addWidget(self.copy_diagnostics)
        actions.addStretch()
        actions.addWidget(close)
        layout.addLayout(actions)

    @Slot()
    def _copy_diagnostics(self) -> None:
        if self.diagnostic_worker is not None:
            return
        self.copy_reset.stop()
        self.copy_diagnostics.setEnabled(False)
        bind(self.copy_diagnostics, tr("Collecting diagnostics…"))
        worker = _DiagnosticWorker()
        worker.signals.completed.connect(self._diagnostics_ready)
        self.diagnostic_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _diagnostics_ready(self, report: str) -> None:
        self.diagnostic_worker = None
        self.copy_diagnostics.setEnabled(True)
        if not self.isVisible():
            self._reset_copy_label()
            return
        QApplication.clipboard().setText(report)
        bind(self.copy_diagnostics, tr("Copied"))
        self.copy_reset.start(2000)

    @Slot()
    def _reset_copy_label(self) -> None:
        bind(self.copy_diagnostics, tr("Copy diagnostic information"))

    def _update_status(self, message: object) -> None:
        if isinstance(message, str):
            bind(self.update_status, message)
            self.update_status.setVisible(bool(message))
