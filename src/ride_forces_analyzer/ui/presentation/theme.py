"""Application-wide presentation themes, independent of scientific/export data.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from typing import Literal
from ride_forces_analyzer.rendering.airtime_colors import VERTICAL_CONTEXT_COLORS
from ride_forces_analyzer.storage.preferences import Appearance

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ride_forces_analyzer.ui.presentation.chrome import (
    install_access_key_cues,
    install_native_captions,
)


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
QMenu { background: #111c29; border: 1px solid #3a4d66; }
QMenu::item:selected:enabled { background: #245fe5; color: white; }
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

ThemeName = Literal[
    Appearance.DARK,
    Appearance.LIGHT,
    Appearance.VERBOLTEN,
    Appearance.MANTA,
    Appearance.FALCONS_FLIGHT,
    Appearance.TARON,
    Appearance.RED_FORCE,
    Appearance.LOCH_NESS,
    Appearance.SLINKY_DOG_DASH,
    Appearance.TOP_THRILL_2,
]


def system_theme(application: QApplication) -> ThemeName:
    """Follow the current effective OS scheme, including scheduled changes.

    Args:
        application: Native Qt application whose event loop owns the widgets.

    Returns:
        Effective light or dark system appearance.
    """
    return (
        Appearance.LIGHT
        if application.styleHints().colorScheme() == Qt.ColorScheme.Light
        else Appearance.DARK
    )


@dataclass(frozen=True, slots=True)
class Theme:
    """Theme contract and owned data.

    Attributes:
        name: Stable identifier or displayed name for this model or view.
        background: Application background color.
        panel: Background color for panels.
        text: Presentation text or source template to bind.
        muted: Color for secondary text.
        grid: Color for chart grid lines.
        border: Color for borders.
        forces: Colors assigned to force channels.
        raw: Colors assigned to retained source channels.
        markers: Source-sample markers or their display colors, as declared by this class.
        accent: Color highlighting the current selection.
        link: Color used for links.
        accent_text: Text color on accent backgrounds.
        chart_background: Chart background color.
        chart_foreground: Chart foreground color.
        chart_forces: Force-channel colors on the chart background.
        chart_raw: Source-channel colors on the chart background.
    """

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
    accent: str = "#245fe5"
    link: str = "#4383ff"
    accent_text: str = "#ffffff"
    chart_background: str | None = None
    chart_foreground: str | None = None
    chart_forces: tuple[str, str, str] | None = None
    chart_raw: tuple[str, str, str] | None = None

    @property
    def is_dark(self) -> bool:
        """Return whether this workspace theme uses its dark palette.

        Returns:
            Whether this workspace theme uses its dark palette.
        """
        return QColor(self.background).lightness() < 128

    @property
    def vertical_context_colors(self) -> dict[str, str]:
        """Return the semantic vertical-force context colors for this theme.

        Returns:
            The semantic vertical-force context colors for this theme.
        """
        if self.is_dark:
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
        """Build the Qt stylesheet for the selected workspace palette.

        Returns:
            Qt stylesheet for the selected theme.
        """
        sheet = STYLESHEET + CONTROL_STYLESHEET
        if self.name is Appearance.DARK:
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
        if self.name is Appearance.VERBOLTEN:
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": "#14251b",
                "#2b394a": "#304c39",
                "#223044": "#24422e",
                "#35465c": self.border,
                "#2d4059": "#31563c",
                "#6885a8": "#83ab8c",
                "#718096": "#718e78",
                "#9eb0c7": self.muted,
                "#b8c9df": "#c7dfcb",
                "#182330": self.panel,
                "#2b3b4d": "#365940",
                "#111c29": "#132219",
                "#2e4055": "#365940",
                "#3a4d66": self.border,
                "#60718b": "#779d81",
                "#36465a": "#37513e",
                "#4383ff": self.link,
                "#d6e5ff": "#ddf2df",
                "#538fff": "#83c98e",
                "#748196": "#809487",
                "#15202d": "#14251b",
                "#40546c": "#4d7057",
                "#101a27": "#132219",
                "#a9bdd5": self.muted,
                "#627d9f": "#83ab8c",
                "#245fe5": self.accent,
                "#5088ff": "#83c98e",
                "#2866df": self.accent,
                "#6c9dff": "#83c98e",
            }
        if self.name is Appearance.MANTA:
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": "#173f68",
                "#2b394a": "#426c91",
                "#223044": "#225780",
                "#35465c": self.border,
                "#2d4059": "#2d6a93",
                "#6885a8": "#a875a4",
                "#718096": "#8ba6ba",
                "#9eb0c7": self.muted,
                "#b8c9df": "#bfe8d4",
                "#182330": self.panel,
                "#2b3b4d": "#426c91",
                "#111c29": "#0d2340",
                "#2e4055": "#426c91",
                "#3a4d66": self.border,
                "#60718b": self.border,
                "#36465a": "#355676",
                "#4383ff": self.link,
                "#d6e5ff": "#c8f3df",
                "#538fff": self.accent,
                "#748196": "#8ba6ba",
                "#15202d": "#173f68",
                "#40546c": "#5987aa",
                "#101a27": "#0d2340",
                "#a9bdd5": self.muted,
                "#627d9f": "#a875a4",
                "#245fe5": self.accent,
                "#5088ff": "#a875a4",
                "#2866df": self.accent,
                "#6c9dff": "#a875a4",
                "white": self.accent_text,
            }
        elif self.name is Appearance.FALCONS_FLIGHT:
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": "#ece1cf",
                "#2b394a": "#d0bda5",
                "#223044": "#eee2d1",
                "#35465c": self.border,
                "#2d4059": "#e2cfb8",
                "#6885a8": "#9d7b5c",
                "#718096": "#817260",
                "#9eb0c7": self.muted,
                "#b8c9df": "#65513e",
                "#182330": self.panel,
                "#2b3b4d": "#d0bda5",
                "#111c29": self.panel,
                "#2e4055": "#d0bda5",
                "#3a4d66": self.border,
                "#60718b": "#9b8269",
                "#36465a": "#d6c3ac",
                "#4383ff": self.link,
                "#d6e5ff": self.panel,
                "#538fff": self.accent,
                "#748196": "#aa9b87",
                "#15202d": "#ece1cf",
                "#40546c": "#b8a086",
                "#101a27": self.panel,
                "#a9bdd5": self.muted,
                "#627d9f": "#9d7b5c",
                "#245fe5": self.accent,
                "#5088ff": "#ba7057",
                "#2866df": self.accent,
                "#6c9dff": "#ba7057",
            }
        elif self.name is Appearance.TARON:
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": "#212426",
                "#2b394a": "#454948",
                "#223044": "#363a3b",
                "#35465c": self.border,
                "#2d4059": "#4a4e4d",
                "#6885a8": "#a69b85",
                "#718096": "#858582",
                "#9eb0c7": self.muted,
                "#b8c9df": "#d3c7b3",
                "#182330": self.panel,
                "#2b3b4d": "#4d514e",
                "#111c29": "#1d2022",
                "#2e4055": "#4d514e",
                "#3a4d66": self.border,
                "#60718b": "#8e9088",
                "#36465a": "#4a4c46",
                "#4383ff": self.link,
                "#d6e5ff": "#e7d0ac",
                "#538fff": self.accent,
                "#748196": "#8b8c84",
                "#15202d": "#212426",
                "#40546c": "#6c7068",
                "#101a27": "#1d2022",
                "#a9bdd5": self.muted,
                "#627d9f": "#a69b85",
                "#245fe5": self.accent,
                "#5088ff": "#d6b88a",
                "#2866df": self.accent,
                "#6c9dff": "#d6b88a",
                "white": self.accent_text,
            }
        elif self.name is Appearance.RED_FORCE:
            sheet += (
                "QCheckBox#forceVisibility, QLabel#airtimeLegend { "
                f"background: {self.panel}; border-radius: 4px; padding: 3px 6px; "
                "}"
            )
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": self.background,
                "#2b394a": "#ffeb00",
                "#223044": self.accent,
                "#35465c": self.border,
                "#2d4059": "#ed2525",
                "#6885a8": "#ffeb00",
                "#718096": "#b7a7a7",
                "#9eb0c7": self.muted,
                "#b8c9df": "#fff4af",
                "#182330": "#990000",
                "#2b3b4d": "#ef3939",
                "#111c29": self.panel,
                "#2e4055": "#6d6d61",
                "#3a4d66": self.border,
                "#60718b": "#ffeb00",
                "#36465a": "#480000",
                "#4383ff": self.link,
                "#d6e5ff": "#ffeb00",
                "#538fff": self.accent,
                "#748196": "#b7a7a7",
                "#15202d": "#990000",
                "#40546c": "#e03b3b",
                "#101a27": self.panel,
                "#a9bdd5": self.muted,
                "#627d9f": "#ffeb00",
                "#245fe5": self.accent,
                "#5088ff": "#ffeb00",
                "#2866df": self.accent,
                "#6c9dff": "#ffeb00",
            }
        elif self.name is Appearance.LOCH_NESS:
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": "#55584f",
                "#2b394a": "#84877d",
                "#223044": "#173f2d",
                "#35465c": self.border,
                "#2d4059": "#255540",
                "#6885a8": "#b63d2e",
                "#718096": "#9a9e88",
                "#9eb0c7": self.muted,
                "#b8c9df": self.accent,
                "#182330": self.panel,
                "#2b3b4d": "#777b6b",
                "#111c29": "#173f2d",
                "#2e4055": "#758671",
                "#3a4d66": self.border,
                "#60718b": "#9b9a8b",
                "#36465a": "#575d4d",
                "#4383ff": self.link,
                "#d6e5ff": self.accent,
                "#538fff": "#b63d2e",
                "#748196": "#9a9e88",
                "#15202d": "#55584f",
                "#40546c": "#929780",
                "#101a27": "#173f2d",
                "#a9bdd5": self.muted,
                "#627d9f": "#b63d2e",
                "#245fe5": self.accent,
                "#5088ff": "#b63d2e",
                "#2866df": self.accent,
                "#6c9dff": "#b63d2e",
                "white": self.accent_text,
            }
        elif self.name is Appearance.SLINKY_DOG_DASH:
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": "#f7e3b4",
                "#2b394a": self.border,
                "#223044": "#f5d489",
                "#35465c": self.border,
                "#2d4059": "#efc263",
                "#6885a8": "#c92520",
                "#718096": "#837766",
                "#9eb0c7": self.muted,
                "#b8c9df": "#8e493a",
                "#182330": self.panel,
                "#2b3b4d": self.border,
                "#111c29": self.panel,
                "#2e4055": self.border,
                "#3a4d66": self.border,
                "#60718b": "#8e493a",
                "#36465a": "#dec99e",
                "#4383ff": self.link,
                "#d6e5ff": self.panel,
                "#538fff": self.accent,
                "#748196": "#b1a38c",
                "#15202d": "#f7e3b4",
                "#40546c": "#b8a57d",
                "#101a27": self.panel,
                "#a9bdd5": self.muted,
                "#627d9f": "#8e493a",
                "#245fe5": self.accent,
                "#5088ff": "#c92520",
                "#2866df": "#4b8c24",
                "#6c9dff": "#4b8c24",
                "white": self.accent_text,
            }
        elif self.name is Appearance.TOP_THRILL_2:
            replacements = {
                "#101720": self.background,
                "#e3ebf5": self.text,
                "#151f2b": self.accent,
                "#2b394a": self.border,
                "#223044": self.panel,
                "#35465c": self.border,
                "#2d4059": "#dcebf5",
                "#6885a8": self.link,
                "#718096": self.muted,
                "#9eb0c7": self.muted,
                "#b8c9df": self.accent,
                "#182330": self.panel,
                "#2b3b4d": self.border,
                "#111c29": self.background,
                "#2e4055": self.border,
                "#3a4d66": self.border,
                "#60718b": self.border,
                "#36465a": "#bbc6ce",
                "#4383ff": self.link,
                "#d6e5ff": self.background,
                "#538fff": self.link,
                "#748196": self.border,
                "#15202d": self.panel,
                "#40546c": self.border,
                "#101a27": self.background,
                "#a9bdd5": self.accent_text,
                "#627d9f": self.link,
                "#245fe5": self.accent,
                "#5088ff": self.link,
                "#2866df": self.link,
                "#6c9dff": self.link,
            }
            sheet += (
                "QToolBar QLabel { color: white; }"
                "QToolBar QPushButton, QToolBar QToolButton { "
                f"background: {self.accent}; color: white; border-color: white; "
                "}"
                "QToolBar QPushButton:hover, QToolBar QToolButton:hover, "
                "QToolBar QPushButton:checked, QToolBar QToolButton:checked { "
                f"background: {self.link}; border-color: white; "
                "}"
                "QToolBar QPushButton:disabled, QToolBar QToolButton:disabled { "
                "color: white; border-style: dashed; "
                "}"
            )
        for source, target in replacements.items():
            sheet = sheet.replace(source, target)
        return sheet


THEMES: dict[ThemeName, Theme] = {
    Appearance.TOP_THRILL_2: Theme(
        Appearance.TOP_THRILL_2,
        "#ffffff",
        "#f2f5f8",
        "#101820",
        "#596773",
        "#596773",
        "#596773",
        ("#0069b4", "#08783b", "#c6253b"),
        ("#245ac4", "#b44909", "#08783b"),
        ("#bb9aff", "#ff8ca8", "#50c4d4", "#ffd07b"),
        accent="#b00020",
        link="#005b96",
        chart_background="#07121c",
        chart_foreground="#ffffff",
        chart_forces=("#009cff", "#22c55e", "#ff374b"),
        chart_raw=("#439aff", "#ff9c54", "#42d999"),
    ),
    Appearance.SLINKY_DOG_DASH: Theme(
        Appearance.SLINKY_DOG_DASH,
        "#fff4d6",
        "#fffbee",
        "#3b241a",
        "#735844",
        "#e5d4ad",
        "#9a9589",
        ("#0069b4", "#08783b", "#c6253b"),
        ("#245ac4", "#b44909", "#08783b"),
        ("#7042b0", "#b4234e", "#087d8b", "#986000"),
        accent="#e8a329",
        link="#4b8c24",
        accent_text="#3b241a",
    ),
    Appearance.DARK: Theme(
        Appearance.DARK,
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
    Appearance.LIGHT: Theme(
        Appearance.LIGHT,
        "#f3f6fa",
        "#ffffff",
        "#172b42",
        "#475d76",
        "#dbe4ef",
        "#9cacc0",
        ("#0069b4", "#08783b", "#c6253b"),
        ("#245ac4", "#b44909", "#08783b"),
        ("#7042b0", "#b4234e", "#087d8b", "#986000"),
        link="#245fe5",
    ),
    Appearance.VERBOLTEN: Theme(
        Appearance.VERBOLTEN,
        "#101c16",
        "#182a20",
        "#e6f0e7",
        "#b2c9b5",
        "#334d3b",
        "#55765f",
        ("#009cff", "#22c55e", "#ff374b"),
        ("#439aff", "#ff9c54", "#42d999"),
        ("#bb9aff", "#ff8ca8", "#50c4d4", "#ffd07b"),
        accent="#397d49",
        link="#83c98e",
    ),
    Appearance.MANTA: Theme(
        Appearance.MANTA,
        "#1c4d7a",
        "#102b49",
        "#eaf8f5",
        "#bddbdc",
        "#355676",
        "#85cbed",
        ("#009cff", "#22c55e", "#ff374b"),
        ("#439aff", "#ff9c54", "#42d999"),
        ("#bb9aff", "#ff8ca8", "#50c4d4", "#ffd07b"),
        accent="#8ad7b2",
        link="#85cbed",
        accent_text="#102b49",
    ),
    Appearance.FALCONS_FLIGHT: Theme(
        Appearance.FALCONS_FLIGHT,
        "#f5efe3",
        "#fffbf3",
        "#352b25",
        "#6c5c4c",
        "#e0d2bf",
        "#b69b7d",
        ("#0069b4", "#08783b", "#c6253b"),
        ("#245ac4", "#b44909", "#08783b"),
        ("#7042b0", "#b4234e", "#087d8b", "#986000"),
        accent="#a54d35",
        link="#92422f",
    ),
    Appearance.TARON: Theme(
        Appearance.TARON,
        "#17191b",
        "#292d30",
        "#e7e2d7",
        "#beb9ad",
        "#414648",
        "#656761",
        ("#009cff", "#22c55e", "#ff374b"),
        ("#439aff", "#ff9c54", "#42d999"),
        ("#bb9aff", "#ff8ca8", "#50c4d4", "#ffd07b"),
        accent="#b9824b",
        link="#6793af",
        accent_text="#17191b",
    ),
    Appearance.RED_FORCE: Theme(
        Appearance.RED_FORCE,
        "#d40000",
        "#000000",
        "#ffffff",
        "#fff1dc",
        "#3c3c3c",
        "#ffeb00",
        ("#009cff", "#22c55e", "#ff374b"),
        ("#439aff", "#ff9c54", "#42d999"),
        ("#bb9aff", "#ff8ca8", "#50c4d4", "#ffd07b"),
        accent="#d40000",
        link="#ffeb00",
    ),
    Appearance.LOCH_NESS: Theme(
        Appearance.LOCH_NESS,
        "#65665f",
        "#303730",
        "#fff8df",
        "#d8d0b4",
        "#525b4f",
        "#9b9a8b",
        ("#009cff", "#22c55e", "#ff374b"),
        ("#439aff", "#ff9c54", "#42d999"),
        ("#bb9aff", "#ff8ca8", "#50c4d4", "#ffd07b"),
        accent="#e2bc24",
        link="#e2bc24",
        accent_text="#173f2d",
    ),
}


def apply_theme(application: QApplication, theme: Theme) -> None:
    """Palette covers native Qt surfaces not painted by the shared stylesheet.

    Args:
        application: Native Qt application whose event loop owns the widgets.
        theme: Application appearance palette.

    Returns:
        None.
    """
    install_native_captions(application)
    install_access_key_cues(application)
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, theme.background),
        (QPalette.ColorRole.WindowText, theme.text),
        (QPalette.ColorRole.Base, theme.panel),
        (QPalette.ColorRole.AlternateBase, theme.background),
        (QPalette.ColorRole.Text, theme.text),
        (QPalette.ColorRole.Button, theme.panel),
        (QPalette.ColorRole.ButtonText, theme.text),
        (QPalette.ColorRole.Mid, theme.border),
        (QPalette.ColorRole.ToolTipBase, theme.panel),
        (QPalette.ColorRole.ToolTipText, theme.text),
        (QPalette.ColorRole.Highlight, theme.accent),
        (QPalette.ColorRole.HighlightedText, theme.accent_text),
        (QPalette.ColorRole.Link, theme.link),
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
            QColor("#718096" if theme.is_dark else "#64748b"),
        )
    application.setPalette(palette)
    application.setStyleSheet(theme.stylesheet)
