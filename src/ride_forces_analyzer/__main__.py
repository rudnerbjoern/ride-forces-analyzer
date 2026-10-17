"""Application entry point."""

import sys

from ride_forces_analyzer.config import AppSettings


def main(settings: AppSettings | None = None) -> int:
    from PySide6.QtCore import QThreadPool
    from PySide6.QtWidgets import QApplication

    from ride_forces_analyzer.ui.window import ExplorerWindow

    settings = settings if settings is not None else AppSettings()
    application = QApplication(sys.argv)
    window = ExplorerWindow(settings)
    window.show()
    result = application.exec()
    QThreadPool.globalInstance().waitForDone()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
