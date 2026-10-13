"""Application entry point."""

import sys

from ride_forces_analyzer.config import AppSettings


def main(settings: AppSettings | None = None) -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    settings = settings if settings is not None else AppSettings()
    application = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle(settings.window_title)
    window.resize(settings.window_width, settings.window_height)
    window.setCentralWidget(QLabel("Ride Forces Analyzer — M1 foundation\nImport planned for M2"))
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
