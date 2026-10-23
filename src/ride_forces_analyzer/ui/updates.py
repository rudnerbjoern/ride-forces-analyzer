"""Optional update worker and presentation; no recording or installer access.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from time import time

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from ride_forces_analyzer import __version__
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.error_reporting import record_error
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.updates import AvailableRelease, check_for_update

from .translation import bind


class _Signals(QObject):
    completed = Signal(object)
    failed = Signal()


class UpdateWorker(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            result = check_for_update(__version__)
        except Exception as error:
            record_error("Update discovery", error)
            self.signals.failed.emit()
        else:
            self.signals.completed.emit(result)


class UpdateController(QObject):
    busy_changed = Signal(bool)
    status_changed = Signal(object)

    def __init__(self, parent: QWidget, preferences: Preferences) -> None:
        super().__init__(parent)
        self.window = parent
        self.preferences = preferences
        self.worker: UpdateWorker | None = None
        self.manual = False
        self.stopped = False

    def check(self, *, manual: bool = True) -> None:
        if self.stopped or self.worker is not None:
            return
        now = time()
        if not manual and not self.preferences.update_check_due(now):
            return
        # Record attempts too, so offline starts never repeatedly retry all day.
        self.preferences.remember_update_check(now)
        self.manual = manual
        worker = UpdateWorker()
        worker.signals.completed.connect(self._completed)
        worker.signals.failed.connect(self._failed)
        self.worker = worker
        self.busy_changed.emit(True)
        self.status_changed.emit(tr("Checking GitHub releases…"))
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _completed(self, result: object) -> None:
        self.worker = None
        self.busy_changed.emit(False)
        if self.stopped:
            return
        if not self.manual and not self.preferences.automatic_updates():
            self.status_changed.emit("")
            return
        if isinstance(result, AvailableRelease):
            self.status_changed.emit(tr("New version {0} is available.", result.tag))
            if self.manual or result.tag != self.preferences.skipped_update():
                self._show_release(result)
        elif self.manual:
            self.status_changed.emit(tr("No newer downloadable release is available."))
        else:
            self.status_changed.emit("")

    @Slot()
    def _failed(self) -> None:
        self.worker = None
        self.busy_changed.emit(False)
        if not self.stopped:
            self.status_changed.emit(
                tr("Update check unavailable. Try again later.") if self.manual else "",
            )

    def _show_release(self, release: AvailableRelease) -> None:
        existing = self.window.findChild(QMessageBox, "updateNotice")
        if existing is not None:
            existing.raise_()
            return
        notice = QMessageBox(self.window)
        notice.setObjectName("updateNotice")
        notice.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        notice.setTextFormat(Qt.TextFormat.PlainText)
        notice.setIcon(QMessageBox.Icon.Information)
        bind(notice, tr("Update available"), "windowTitle")
        bind(
            notice,
            tr(
                "Version {0} is available. Installed version: {1}. Open the release page to download it. Nothing is installed automatically.",
                release.tag,
                __version__,
            ),
        )
        open_release = bind(
            notice.addButton(str(tr("Open release")), QMessageBox.ButtonRole.AcceptRole),
            tr("Open release"),
        )
        later = bind(
            notice.addButton(str(tr("Later")), QMessageBox.ButtonRole.RejectRole),
            tr("Later"),
        )
        skip = bind(
            notice.addButton(str(tr("Skip this version")), QMessageBox.ButtonRole.ActionRole),
            tr("Skip this version"),
        )
        notice.setDefaultButton(later)

        def chosen(_result: int) -> None:
            if notice.clickedButton() is open_release:
                QDesktopServices.openUrl(QUrl(release.url))
            elif notice.clickedButton() is skip:
                self.preferences.skip_update(release.tag)

        notice.finished.connect(chosen)
        notice.open()
