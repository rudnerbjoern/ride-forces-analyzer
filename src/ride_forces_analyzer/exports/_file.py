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

    Args:
        path: Filesystem path read or written by this operation.
        encoding: Text encoding passed to the stream.
        newline: Line-ending handling passed to the stream.
        overwrite: Whether the caller explicitly permits replacing an existing
            destination.

    Yields:
        Writable text stream for the new file or temporary replacement.

    Raises:
        FileExistsError: The destination exists and overwrite is disabled.
        OSError: If the required filesystem operation fails.
        BaseException: If the underlying operation fails; the original error is
            propagated.
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
