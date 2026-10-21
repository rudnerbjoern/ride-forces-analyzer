"""File lifecycle for sample exports, including confirmed atomic replacement.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from contextlib import contextmanager, ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TextIO


@contextmanager
def export_file(
    path: Path,
    *,
    encoding: str,
    newline: str,
    overwrite: bool,
) -> Generator[TextIO]:
    """Write exclusively, or replace only after a successful complete write.

    Replacement uses a temporary sibling directory on the same filesystem.
    Writing, closing or replacement failures propagate; existing output survives
    cancellation/failure. Only newly created incomplete output is removed.
    """
    with ExitStack() as stack:
        destination = path
        if overwrite:
            directory = stack.enter_context(
                TemporaryDirectory(prefix=".rfa-export-", dir=path.parent),
            )
            destination = Path(directory) / path.name
        created = False
        try:
            with destination.open("x", encoding=encoding, newline=newline) as stream:
                created = True
                yield stream
            if overwrite:
                destination.replace(path)
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise
