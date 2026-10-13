"""Application entry point."""

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    application = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Ride Forces Analyzer — M1")
    window.resize(900, 600)
    window.setCentralWidget(QLabel("Ride Forces Analyzer — M1 foundation\nImport planned for M2"))
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
