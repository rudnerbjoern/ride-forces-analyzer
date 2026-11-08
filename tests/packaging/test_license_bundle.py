"""Consolidated notices preserve attribution, exceptions and all source associations."""

from importlib import metadata
from pathlib import Path

import pytest

from scripts import build_windows
from scripts.license_bundle import LicenseBundle, read_notice

MIT = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
    "of this software to use it subject to retaining this notice.\n"
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY.\n'
)


def test_shared_terms_appear_once_with_each_library_copyright(tmp_path: Path) -> None:
    bundle = LicenseBundle()
    for name, author, terms in [
        ("first", "Alice", MIT),
        ("second", "Björn", MIT.replace("\n", " ")),
    ]:
        bundle.add(
            name,
            "1.0",
            "MIT",
            [(f"{name}/LICENSE", "MIT", f"MIT License\nCopyright {author}\n\n{terms}")],
        )
    output = tmp_path / "THIRD-PARTY-LICENSES.txt"
    bundle.write(output)
    text = output.read_text(encoding="utf-8")
    assert text.count("Permission is hereby granted") == 1
    assert text.count("===== MIT =====") == 1
    assert "Copyright Alice" in text and "Copyright Björn" in text
    assert "first 1.0 — MIT\n  [L001] first/LICENSE\nMIT License\nCopyright Alice" in text
    assert "second 1.0 — MIT\n  [L001] second/LICENSE\nMIT License\nCopyright Björn" in text
    assert len(bundle.texts) == 1


def test_different_conditions_and_exceptions_are_never_merged(tmp_path: Path) -> None:
    bundle = LicenseBundle()
    for name, extra in [
        ("first", ""),
        ("second", "\nAdditional distribution exception: retain this condition."),
    ]:
        bundle.add(name, "1", "MIT", [("LICENSE", "MIT", MIT + extra)])
    output = tmp_path / "notices.txt"
    bundle.write(output)
    text = output.read_text(encoding="utf-8")
    assert text.count("===== MIT =====") == 1
    assert text.count("Permission is hereby granted") == 2
    assert "Additional distribution exception: retain this condition." in text
    assert len(bundle.texts) == 2


def test_composite_license_prefix_is_not_misclassified_as_attribution(tmp_path: Path) -> None:
    text = "Original license agreement\nPermission to redistribute on these terms.\n\n" + MIT
    bundle = LicenseBundle()
    bundle.add("composite", "1", "Bundled terms", [("COPYING", "Bundled terms", text)])
    assert bundle.components[0].notices[0].attribution == ""
    assert list(bundle.texts.values()) == [text.strip()]


def test_legacy_encoding_preserves_notice_characters(tmp_path: Path) -> None:
    notice = tmp_path / "COPYING"
    notice.write_bytes("Copyright Björn\n".encode("latin-1"))
    assert read_notice(notice) == "Copyright Björn\n"
    notice.write_bytes("Copyright Björn 🧭\n".encode("utf-8"))
    assert read_notice(notice) == "Copyright Björn 🧭\n"


def test_empty_license_component_is_rejected() -> None:
    with pytest.raises(ValueError, match="Missing license notices"):
        LicenseBundle().add("missing", "1", "Unknown", [("LICENSE", "Unknown", " \n")])


def test_collection_preserves_qt_sources_python_scope_and_catalog_without_metadata_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    (root / "packaging").mkdir(parents=True)
    (root / "packaging/redistribution.json").write_text(
        '{"status":"accepted","limitations":["Keep original limitation"]}',
        encoding="utf-8",
    )
    (root / "packaging/QT-NOTICES.txt").write_text(
        "Qt scope: inclusion does not imply every component is linked.\n\n"
        "===== qt/module-a/LICENSES/MIT.txt =====\n"
        + MIT
        + "\n===== qt/module-b/LICENSES/MIT.txt =====\n"
        + MIT,
        encoding="utf-8",
    )
    python = tmp_path / "python"
    python.mkdir()
    (python / "LICENSE.txt").write_text(
        "Complete Python license and bundled-library credits",
        encoding="utf-8",
    )
    info = tmp_path / "site/example-1.0.dist-info"
    (info / "licenses").mkdir(parents=True)
    (info / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: example\nVersion: 1.0\nLicense-Expression: MIT\n\nUNRELATED PACKAGE DESCRIPTION MUST NOT SHIP",
        encoding="utf-8",
    )
    (info / "licenses/LICENSE").write_text("Copyright Example Authors\n\n" + MIT, encoding="utf-8")
    (info / "RECORD").write_text("example-1.0.dist-info/licenses/LICENSE,,\n", encoding="utf-8")
    monkeypatch.setattr(build_windows, "ROOT", root)
    monkeypatch.setattr(build_windows.sys, "base_prefix", str(python))
    monkeypatch.setattr(
        build_windows,
        "runtime_distributions",
        lambda: [metadata.Distribution.at(info)],
    )

    def installed_version(_name: str) -> str:
        return "6.12.0"

    monkeypatch.setattr(build_windows.metadata, "version", installed_version)
    output = tmp_path / "out/THIRD-PARTY-LICENSES.txt"
    bundle = build_windows.collect_notices(output)
    text = output.read_text(encoding="utf-8")
    assert list(output.parent.iterdir()) == [output]
    assert "example 1.0 — MIT" in text
    assert "Copyright Example Authors" in text
    assert "Complete Python license and bundled-library credits" in text
    assert "Keep original limitation" in text
    assert "inclusion does not imply every component is linked" in text
    assert "qt/module-a/LICENSES/MIT.txt" in text
    assert "qt/module-b/LICENSES/MIT.txt" in text
    assert text.count("Permission is hereby granted") == 1
    assert "UNRELATED PACKAGE DESCRIPTION" not in text
    assert len(bundle.components) == 4
