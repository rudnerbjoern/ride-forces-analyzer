"""Application-wide light/dark presentation, independent of scientific/export data.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from typing import Literal
from ride_forces_analyzer.airtime_colors import VERTICAL_CONTEXT_COLORS

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


# cspell:words Segoe gridline

STYLESHEET = """
QMainWindow, QDialog { background: #101720; color: #e3ebf5; }
QWidget#InspectorBody { background: #101720; }
QWidget { font-size: 9pt; color: #e3ebf5; }
QToolBar { background: #151f2b; border: 0; border-bottom: 1px solid #2b394a; spacing: 8px; padding: 4px; }
QToolBar QLabel { font-weight: 600; padding: 0 10px 0 4px; }
QPushButton, QToolButton { background: #223044; border: 1px solid #35465c; border-radius: 6px; padding: 6px 10px; }
QPushButton:hover, QToolButton:hover { background: #2d4059; border-color: #6885a8; }
QPushButton:checked, QToolButton:checked, QToolButton#Primary { background: #245fe5; border-color: #5088ff; }
QPushButton:disabled, QToolButton:disabled, QCheckBox:disabled { color: #718096; }
QLabel#recordingHeading { font-size: 23px; font-weight: 600; }
QLabel#Muted { color: #9eb0c7; }
QLabel#SectionTitle { color: #b8c9df; font-size: 11px; font-weight: 600; }
QFrame#Panel { background: #182330; border: 1px solid #2b3b4d; border-radius: 10px; }
QFrame#ValueCard { background: #111c29; border: 1px solid #2e4055; border-radius: 7px; }
QLabel#CurrentValue { font-size: 22px; font-weight: 600; }
QLabel { background: transparent; border: 0; }
QSpinBox { background: #111c29; border: 1px solid #3a4d66; border-radius: 5px; padding: 4px; }
QSpinBox:disabled { color: #718096; }
QCheckBox { spacing: 5px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QCheckBox::indicator:unchecked { background: #111c29; border: 1px solid #60718b; border-radius: 3px; }
QCheckBox::indicator:checked { background: #2866df; border: 1px solid #6c9dff; border-radius: 3px; }
QSlider { background: transparent; }
QSlider::groove:horizontal { background: #36465a; height: 4px; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4383ff; border-radius: 2px; }
QSlider::handle:horizontal { background: #d6e5ff; border: 2px solid #538fff; width: 12px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:disabled { background: #748196; border-color: #748196; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: #15202d; width: 8px; }
QScrollBar::handle:vertical { background: #40546c; min-height: 24px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #101720; }
QPlainTextEdit { background: #101a27; border: 1px solid #35465c; border-radius: 5px; padding: 6px; }
QStatusBar { background: #151f2b; color: #a9bdd5; border-top: 1px solid #2b394a; }
QStatusBar::item { border: none; }
QProgressBar { border: 0; background: #223044; max-height: 4px; }
QProgressBar::chunk { background: #4383ff; }
QToolTip { background: #223044; color: #e3ebf5; border: 1px solid #627d9f; padding: 6px; }
"""

CONTROL_STYLESHEET = """
QComboBox, QDoubleSpinBox, QLineEdit, QListWidget, QTableWidget, QTextEdit {
    background: #111c29; border: 1px solid #3a4d66; border-radius: 5px; padding: 4px;
    selection-background-color: #245fe5; selection-color: white;
}
QComboBox QAbstractItemView { background: #111c29; color: #e3ebf5; selection-background-color: #245fe5; selection-color: white; }
QHeaderView::section { background: #223044; color: #e3ebf5; border: 1px solid #35465c; padding: 5px; }
QTableWidget { gridline-color: #35465c; }
QPushButton:checked, QToolButton:checked, QToolButton#Primary { color: white; }
QComboBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled { color: #718096; }
QToolBar QPushButton, QToolBar QToolButton, QToolBar QComboBox {
    min-height: 20px; max-height: 20px; padding: 6px 10px;
}
"""

ThemeName = Literal["dark", "light"]


def system_theme(application: QApplication) -> ThemeName:
    """Follow the current effective OS scheme, including scheduled changes."""
    return "light" if application.styleHints().colorScheme() == Qt.ColorScheme.Light else "dark"


@dataclass(frozen=True, slots=True)
class Theme:
    name: ThemeName
    background: str
    panel: str
    text: str
    muted: str
    grid: str
    border: str
    forces: tuple[str, str, str]
    raw: tuple[str, str, str]
    markers: tuple[str, str, str, str]

    @property
    def vertical_context_colors(self) -> dict[str, str]:
        if self.name == "dark":
            return dict(VERTICAL_CONTEXT_COLORS)
        return {
            "Heavy Gs": "#7040a0",
            "Normal Gs": "#555555",
            "Light Gs": "#285b91",
            "Floater Airtime": "#006578",
            "Airtime": "#756000",
            "Strong Airtime": "#964500",
            "Ejector Airtime": "#b1253a",
        }

    @property
    def stylesheet(self) -> str:
        sheet = STYLESHEET + CONTROL_STYLESHEET
        if self.name == "dark":
            return sheet
        replacements = {
            "#101720": "#f3f6fa",
            "#e3ebf5": "#172b42",
            "#151f2b": "#e9eff6",
            "#2b394a": "#c6d3e2",
            "#223044": "#e3ebf5",
            "#35465c": "#b7c7da",
            "#2d4059": "#d4e2f3",
            "#6885a8": "#617e9e",
            "#718096": "#64748b",
            "#9eb0c7": "#475d76",
            "#b8c9df": "#3c536e",
            "#182330": "#ffffff",
            "#2b3b4d": "#c6d3e2",
            "#111c29": "#ffffff",
            "#2e4055": "#c6d3e2",
            "#3a4d66": "#9cacc0",
            "#60718b": "#71869f",
            "#36465a": "#bdcce0",
            "#4383ff": "#245fe5",
            "#d6e5ff": "#ffffff",
            "#538fff": "#245fe5",
            "#748196": "#94a3b8",
            "#15202d": "#e9eff6",
            "#40546c": "#91a5be",
            "#101a27": "#ffffff",
            "#a9bdd5": "#475d76",
            "#627d9f": "#617e9e",
        }
        for source, target in replacements.items():
            sheet = sheet.replace(source, target)
        return sheet


THEMES: dict[ThemeName, Theme] = {
    "dark": Theme(
        "dark",
        "#101720",
        "#182330",
        "#e3ebf5",
        "#b7c9df",
        "#314153",
        "#536981",
        ("#009cff", "#22c55e", "#ff374b"),
        ("#2563eb", "#ea580c", "#059669"),
        ("#bb9aff", "#ff8ca8", "#50c4d4", "#ffd07b"),
    ),
    "light": Theme(
        "light",
        "#f3f6fa",
        "#ffffff",
        "#172b42",
        "#475d76",
        "#dbe4ef",
        "#9cacc0",
        ("#0069b4", "#08783b", "#c6253b"),
        ("#245ac4", "#b44909", "#08783b"),
        ("#7042b0", "#b4234e", "#087d8b", "#986000"),
    ),
}


def apply_theme(application: QApplication, theme: Theme) -> None:
    """Palette covers native Qt surfaces not painted by the shared stylesheet."""
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, theme.background),
        (QPalette.ColorRole.WindowText, theme.text),
        (QPalette.ColorRole.Base, theme.panel),
        (QPalette.ColorRole.AlternateBase, theme.background),
        (QPalette.ColorRole.Text, theme.text),
        (QPalette.ColorRole.Button, theme.panel),
        (QPalette.ColorRole.ButtonText, theme.text),
        (QPalette.ColorRole.ToolTipBase, theme.panel),
        (QPalette.ColorRole.ToolTipText, theme.text),
        (QPalette.ColorRole.Highlight, "#245fe5"),
        (QPalette.ColorRole.HighlightedText, "#ffffff"),
        (QPalette.ColorRole.Link, "#4383ff" if theme.name == "dark" else "#245fe5"),
        (QPalette.ColorRole.PlaceholderText, theme.muted),
    ):
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            role,
            QColor("#718096" if theme.name == "dark" else "#64748b"),
        )
    application.setPalette(palette)
    application.setStyleSheet(theme.stylesheet)
