"""Source releases reject mismatched tags, changed originals and private artifacts."""

from collections.abc import Callable
from hashlib import sha256
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from typing import cast
from zipfile import ZipFile

import pytest

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / ".github/scripts/check-source-release.py"),
)
validate_archive = cast(Callable[[Path, str], None], MODULE["validate_archive"])
REQUIRED_FILES = cast(tuple[str, ...], MODULE["REQUIRED_FILES"])


@pytest.mark.parametrize(
    "change,tag,error",
    [
        ("none", "v0.1.0", None),
        ("export-tests", "v0.1.0", None),
        ("local-exports", "v0.1.0", "unexpected"),
        ("none", "v0.3.1", "project.version"),
        ("recording", "v0.1.0", "integrity"),
        ("rfdb-recording", "v0.1.0", "integrity"),
        ("missing-rfdb-recording", "v0.1.0", "inventory"),
        ("extra-recording", "v0.1.0", "inventory"),
        ("missing-license", "v0.1.0", "required"),
        ("private-file", "v0.1.0", "unexpected"),
        ("binary", "v0.1.0", "unexpected"),
    ],
)
def test_source_archive_contract(change: str, tag: str, error: str | None) -> None:
    recording = b'{"synthetic":true}'
    files = dict.fromkeys(REQUIRED_FILES, b"synthetic source/license content")
    files["pyproject.toml"] = b'[project]\nversion = "0.1.0"\nlicense = "GPL-3.0-or-later"\n'
    files["tests/fixtures/schema-inventory.json"] = json.dumps(
        {
            "fixtures": {
                "example.forces": {
                    "byte_count": len(recording),
                    "sha256": sha256(recording).hexdigest(),
                },
            },
        },
    ).encode()
    files["tests/fixtures/real/example.forces"] = recording
    files["tests/fixtures/rfdb-schema-inventory.json"] = files[
        "tests/fixtures/schema-inventory.json"
    ]
    files["tests/fixtures/rfdb/example.forces"] = recording
    if change == "export-tests":
        files["tests/exports/test_csv_export.py"] = b"# Supported source tests\n"
    elif change == "local-exports":
        files["exports/private.csv"] = b"private output"
    elif change == "recording":
        files["tests/fixtures/real/example.forces"] = b"changed"
    elif change == "rfdb-recording":
        files["tests/fixtures/rfdb/example.forces"] = b"changed"
    elif change == "missing-rfdb-recording":
        del files["tests/fixtures/rfdb/example.forces"]
    elif change == "extra-recording":
        files["tests/fixtures/real/additional.forces"] = recording
    elif change == "missing-license":
        del files["LICENSE"]
    elif change == "private-file":
        files[".tmp/private.log"] = b"private"
    elif change == "binary":
        files["ffmpeg.exe"] = b"binary"
    with TemporaryDirectory(dir=".tmp") as directory:
        archive = Path(directory) / "source.zip"
        with ZipFile(archive, "w") as source:
            for name, data in files.items():
                source.writestr(name, data)
        before = archive.read_bytes()
        if error is None:
            validate_archive(archive, tag)
        else:
            with pytest.raises(ValueError, match=error):
                validate_archive(archive, tag)
        assert archive.read_bytes() == before
