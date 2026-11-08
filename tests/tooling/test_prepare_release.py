"""Version preparation preserves independent targets and explicit protocol approval."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import pytest

from scripts import prepare_release
from scripts.prepare_release import (
    MANIFEST,
    PLUGIN,
    prepare_interfaces,
    prepare_versions,
    ReleaseEdits,
)

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "pyproject.toml",
    "uv.lock",
    "src/ride_forces_analyzer/__init__.py",
    "README.md",
    "package-lock.json",
    (PLUGIN / "package.json").as_posix(),
    MANIFEST.as_posix(),
    "src/ride_forces_analyzer/runtime/control_contract.py",
    "src/ride_forces_analyzer/runtime/stream_deck.py",
    (PLUGIN / "src/protocol.ts").as_posix(),
    (PLUGIN / "src/transport.ts").as_posix(),
    "tests/support/test_control_contract.py",
    "tests/fixtures/stream_deck_protocol.json",
    "docs/architecture/06_runtime_view.md",
    "docs/implementation/STREAM_DECK.md",
    (PLUGIN / "README.md").as_posix(),
    "docs/images/README.md",
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for name in FILES:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    # Exercise fixed synthetic releases independently of the checkout's version.
    for name, pattern, version in (
        (FILES[0], r'(?m)^(version = ")[^"]+("\r?$)', "2.0.0"),
        (FILES[1], r'(name = "ride-forces-analyzer"\r?\nversion = ")[^"]+(")', "2.0.0"),
        (FILES[2], r'(__version__ = ")[^"]+(")', "2.0.0"),
        (FILES[3], r"(Version \*\*)[^*]+(\*\* is a stable release\.)", "2.0.0"),
        (
            FILES[4],
            r'("plugins/stream-deck": \{\r?\n\s*"name": "@ride-forces-analyzer/stream-deck",\r?\n\s*"version": ")[^"]+(")',
            "0.2.0",
        ),
        (FILES[5], r'("version": ")[^"]+(")', "0.2.0"),
        (FILES[6], r'("Version": ")[^"]+(")', "0.2.0.0"),
    ):
        file = tmp_path / name
        content, count = re.subn(
            pattern,
            lambda match: f"{match[1]}{version}{match[2]}",
            file.read_text(encoding="utf-8"),
            count=1,
        )
        assert count == 1
        file.write_text(content, encoding="utf-8", newline="\n")
    return tmp_path


def snapshot(root: Path) -> dict[str, bytes]:
    return {name: (root / name).read_bytes() for name in FILES}


@pytest.mark.parametrize("version,status", [("2.1.0", "stable"), ("2.1.0rc1", "preview")])
def test_app_versions_sync_without_touching_plugin_protocol_or_dependencies(
    repository: Path,
    version: str,
    status: str,
) -> None:
    before = snapshot(repository)
    edits = prepare_versions(repository, app=version)
    changed = edits.apply()
    assert set(changed) == {Path(name) for name in FILES[:4]}
    assert (
        tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "version"
        ]
        == version
    )
    assert f'__version__ = "{version}"' in (repository / FILES[2]).read_text(encoding="utf-8")
    lock = tomllib.loads((repository / "uv.lock").read_text(encoding="utf-8"))
    assert (
        next(p for p in lock["package"] if p["name"] == "ride-forces-analyzer")["version"]
        == version
    )
    assert f"Version **{version}** is a {status} release." in (repository / "README.md").read_text(
        encoding="utf-8",
    )
    old_packages = tomllib.loads(before["uv.lock"].decode())["package"]
    assert [p for p in lock["package"] if p["name"] != "ride-forces-analyzer"] == [
        p for p in old_packages if p["name"] != "ride-forces-analyzer"
    ]
    assert all(
        (repository / name).read_bytes() == content
        for name, content in before.items()
        if Path(name) not in changed
    )


def test_plugin_metadata_is_independent_and_idempotent(repository: Path) -> None:
    before = json.loads((repository / "package-lock.json").read_text(encoding="utf-8"))
    changed = prepare_versions(repository, plugin="0.3.0").apply()
    assert set(changed) == {PLUGIN / "package.json", MANIFEST, Path("package-lock.json")}
    assert json.loads((repository / MANIFEST).read_text(encoding="utf-8"))["Version"] == "0.3.0.0"
    lock = json.loads((repository / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"]["plugins/stream-deck"].pop("version") == "0.3.0"
    before["packages"]["plugins/stream-deck"].pop("version")
    assert lock == before
    assert prepare_versions(repository, plugin="0.3.0").apply() == []


@pytest.mark.parametrize("value", ["v2.1.0", "02.1.0", "2.1", "2.1.0-beta", "2.65536.0", "1.9.0"])
def test_invalid_or_decreasing_targets_never_write(repository: Path, value: str) -> None:
    before = snapshot(repository)
    with pytest.raises(ValueError):
        prepare_versions(repository, app=value).apply()
    assert snapshot(repository) == before


def test_plugin_rejects_preview_versions_and_preserves_all_files(repository: Path) -> None:
    before = snapshot(repository)
    with pytest.raises(ValueError):
        prepare_versions(repository, app="2.1.0", plugin="0.3.0rc1").apply()
    assert snapshot(repository) == before


def test_metadata_drift_rejects_the_entire_plan(repository: Path) -> None:
    (repository / MANIFEST).write_text('{"Version": "99.0.0.0"}', encoding="utf-8")
    before = snapshot(repository)
    with pytest.raises(ValueError, match="Unexpected version fields"):
        prepare_versions(repository, app="2.1.0", plugin="0.3.0").apply()
    assert snapshot(repository) == before


def test_preview_and_product_updates_leave_the_protocol_lock_untouched(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = snapshot(repository)
    edits = prepare_versions(repository, app="2.1.0", plugin="0.3.0")
    prepare_interfaces(edits)
    assert len(edits.apply(dry_run=True)) == 7
    assert "2.1.0" in capsys.readouterr().out
    assert snapshot(repository) == before
    edits.apply()
    assert (repository / "tests/support/test_control_contract.py").read_bytes() == before[
        "tests/support/test_control_contract.py"
    ]
    assert (
        repository / "src/ride_forces_analyzer/runtime/control_contract.py"
    ).read_bytes() == before["src/ride_forces_analyzer/runtime/control_contract.py"]


def test_explicit_interface_targets_sync_sources_examples_docs_and_locked_baseline(
    repository: Path,
) -> None:
    edits = ReleaseEdits(repository)
    prepare_interfaces(edits, control=4, transport=4)
    edits.apply()
    assert "PROTOCOL_VERSION = 4;" in (repository / PLUGIN / "src/protocol.ts").read_text(
        encoding="utf-8",
    )
    assert "PROTOCOL_VERSION = 4\n" in (
        repository / "src/ride_forces_analyzer/runtime/control_contract.py"
    ).read_text(encoding="utf-8")
    freeze = (repository / "tests/support/test_control_contract.py").read_text(encoding="utf-8")
    assert "assert PROTOCOL_VERSION == 4, message" in freeze
    assert "Protocol version 4 is owner-approved" in freeze
    assert "TRANSPORT_VERSION = 4\n" in (
        repository / "src/ride_forces_analyzer/runtime/stream_deck.py"
    ).read_text(encoding="utf-8")
    transport = (repository / PLUGIN / "src/transport.ts").read_text(encoding="utf-8")
    assert "version: 1" not in transport
    assert "ready.version !== 4" in transport
    assert "following protocol 2 in app release v2.0.0" in (
        repository / "docs/architecture/06_runtime_view.md"
    ).read_text(encoding="utf-8")
    edits = ReleaseEdits(repository)
    prepare_interfaces(edits, control=5)
    edits.apply()
    assert "ready.version !== 4" in (repository / PLUGIN / "src/transport.ts").read_text(
        encoding="utf-8",
    )


@pytest.mark.parametrize("target", [0, -1, True, 2])
def test_bad_interface_target_preserves_originals(repository: Path, target: int) -> None:
    before = snapshot(repository)
    with pytest.raises(ValueError):
        prepare_interfaces(ReleaseEdits(repository), control=target)
    assert snapshot(repository) == before


@pytest.mark.parametrize("drift", [False, True])
def test_unchanged_interface_target_still_checks_synchronized_fields(
    repository: Path,
    drift: bool,
) -> None:
    source = repository / PLUGIN / "src/protocol.ts"
    if drift:
        source.write_text(
            source.read_text(encoding="utf-8").replace("= 3;", "= 99;"),
            encoding="utf-8",
        )
    before = snapshot(repository)
    edits = ReleaseEdits(repository)
    if drift:
        with pytest.raises(ValueError, match="Unexpected version fields"):
            prepare_interfaces(edits, control=3)
    else:
        prepare_interfaces(edits, control=3, transport=1)
        assert edits.apply() == []
    assert snapshot(repository) == before


def test_line_endings_survive_preparation(repository: Path) -> None:
    for name in FILES:
        file = repository / name
        file.write_bytes(file.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    prepare_versions(repository, app="2.1.0", plugin="0.3.0").apply()
    assert all(b"\n" not in data.replace(b"\r\n", b"") for data in snapshot(repository).values())


@pytest.mark.parametrize("persistent", [False, True])
def test_partial_write_failure_restores_originals(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    persistent: bool,
) -> None:
    before = snapshot(repository)
    original_write = Path.write_bytes
    failed = False

    def write(path: Path, data: bytes) -> int:
        nonlocal failed
        if path.name == "package-lock.json" and (persistent or not failed):
            failed = True
            raise OSError("Synthetic write failure")
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", write)
    with pytest.raises(OSError, match="Synthetic"):
        prepare_versions(repository, app="2.1.0", plugin="0.3.0").apply()
    assert snapshot(repository) == before


def test_preparation_captures_every_group_after_writing_versions(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(prepare_release, "ROOT", repository)
    monkeypatch.setattr(sys, "argv", ["prepare_release", "--app-version", "2.1.0"])
    before_guide = (repository / "docs/images/README.md").read_bytes()

    def run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == repository and check and timeout == 300
        assert command[0] == sys.executable
        assert '__version__ = "2.1.0"' in (repository / FILES[2]).read_text(encoding="utf-8")
        assert (repository / "docs/images/README.md").read_bytes() == before_guide
        calls.append(command[1:])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    prepare_release.main()
    assert calls == [
        ["scripts/generate_app_screenshots.py"],
        ["scripts/generate_app_screenshots.py", "--details"],
        ["scripts/generate_app_screenshots.py", "--themes"],
        ["scripts/generate_export_screenshots.py"],
        ["scripts/generate_stream_deck_screenshots.py"],
    ]
    assert "screenshots show version 2.1.0." in (repository / "docs/images/README.md").read_text(
        encoding="utf-8",
    )


def test_metadata_preview_never_runs_generators_or_changes_files(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = snapshot(repository)
    monkeypatch.setattr(prepare_release, "ROOT", repository)
    monkeypatch.setattr(sys, "argv", ["prepare_release", "--app-version", "2.1.0", "--dry-run"])

    def run(*_arguments: object, **_options: object) -> None:
        pytest.fail("Preview must never start a screenshot generator")

    monkeypatch.setattr(subprocess, "run", run)
    prepare_release.main()
    assert snapshot(repository) == before


@pytest.mark.parametrize("failed_group", [1, 3, 5])
def test_failed_capture_stops_and_can_be_retried_with_the_same_targets(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_group: int,
) -> None:
    monkeypatch.setattr(prepare_release, "ROOT", repository)
    monkeypatch.setattr(sys, "argv", ["prepare_release", "--app-version", "2.1.0"])
    guide = repository / "docs/images/README.md"
    before_guide = guide.read_bytes()
    image = repository / "docs/images/workspace-dark.png"
    calls: list[list[str]] = []

    def run(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        image.write_bytes(b"Output from the attempted capture")
        if len(calls) == failed_group:
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(SystemExit) as failure:
        prepare_release.main()
    assert failure.value.code == 1
    assert len(calls) == failed_group
    assert '__version__ = "2.1.0"' in (repository / FILES[2]).read_text(encoding="utf-8")
    assert image.read_bytes() == b"Output from the attempted capture"
    assert guide.read_bytes() == before_guide
    prepare_release.main()
    assert len(calls) == failed_group + 5
    assert "screenshots show version 2.1.0." in guide.read_text(encoding="utf-8")
