"""Keep Qt's standard GUI dependencies, excluding the unused PDF image plugin.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words hiddenimports datas qpdf libqpdf

from importlib import import_module
from pathlib import Path

hiddenimports: list[str]
binaries: list[tuple[str, str]]
datas: list[tuple[str, str]]
hiddenimports, binaries, datas = import_module("PyInstaller.utils.hooks.qt").add_qt6_dependencies(
    __file__,
)
binaries = [entry for entry in binaries if Path(entry[0]).stem.lower() not in ("qpdf", "libqpdf")]
