"""Qt text bindings and locale switching; no translation of opaque source values.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words qtbase

from collections.abc import Sequence
from typing import TypeVar
from weakref import WeakKeyDictionary

from PySide6.QtCore import QObject, QLocale, QLibraryInfo, QTranslator
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGraphicsSimpleTextItem,
    QListWidget,
    QStatusBar,
    QTableWidget,
)

from ride_forces_analyzer.i18n import Language, Text, set_language

T = TypeVar("T", bound=QObject | QGraphicsSimpleTextItem)
_bindings: WeakKeyDictionary[QObject, dict[str, Text]] = WeakKeyDictionary()
_qt_translator: QTranslator | None = None


def system_ui_language() -> Language:
    """Use the preferred OS display language, not Qt's mutable default locale."""
    languages = QLocale.system().uiLanguages()
    primary = languages[0].lower().replace("_", "-").split("-")[0] if languages else ""
    return "de" if primary == "de" else "en"


def _apply(widget: QObject, prop: str, value: str) -> None:
    if prop.startswith("item:") and isinstance(widget, QComboBox):
        widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        widget.setItemText(int(prop.split(":")[1]), value)
        widget.updateGeometry()
    elif prop.startswith("item:") and isinstance(widget, QListWidget):
        list_item = widget.item(int(prop.split(":")[1]))
        list_item.setText(value)
    elif prop.startswith("header:") and isinstance(widget, QTableWidget):
        item = widget.horizontalHeaderItem(int(prop.split(":")[1]))
        if item is not None:
            item.setText(value)
    elif prop == "message" and isinstance(widget, QStatusBar):
        widget.showMessage(value)
    else:
        widget.setProperty(prop, value)


def bind(widget: T, value: str, prop: str = "text") -> T:
    if isinstance(widget, QGraphicsSimpleTextItem):
        if prop == "toolTip":
            widget.setToolTip(str(value))
        else:
            widget.setText(str(value))
        return widget
    bindings = _bindings.setdefault(widget, {})
    if isinstance(value, Text):
        bindings[prop] = value
    else:
        bindings.pop(prop, None)
    _apply(widget, prop, str(value))
    return widget


def items(combo: QComboBox | QListWidget, values: Sequence[str]) -> None:
    if isinstance(combo, QComboBox):
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    for value in values:
        index = combo.count()
        combo.addItem(str(value))
        bind(combo, value, f"item:{index}")


def headers(table: QTableWidget, values: Sequence[str]) -> None:
    table.setHorizontalHeaderLabels([str(value) for value in values])
    for index, value in enumerate(values):
        bind(table, value, f"header:{index}")


def set_ui_language(application: QApplication, language: Language) -> None:
    global _qt_translator
    set_language(language)
    locale = QLocale("de_DE" if language == "de" else "en_US")
    QLocale.setDefault(locale)
    if _qt_translator is not None:
        application.removeTranslator(_qt_translator)
        _qt_translator = None
    if language == "de":
        translator = QTranslator(application)
        if translator.load(
            "qtbase_de",
            QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
        ):
            application.installTranslator(translator)
            _qt_translator = translator
    for widget, bindings in list(_bindings.items()):
        try:
            for prop, text in bindings.items():
                _apply(widget, prop, str(text))
        except RuntimeError:
            # A retained Python wrapper may outlive its deleted Qt parent.
            _bindings.pop(widget, None)
    for window in application.topLevelWidgets():
        window.setLocale(locale)
