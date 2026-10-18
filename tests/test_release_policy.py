"""Release policy requires reviewed main history and explicit version classification."""

from collections.abc import Callable
from pathlib import Path
import runpy
import subprocess
from tempfile import TemporaryDirectory
from typing import cast

import pytest

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / ".github/scripts/check-release-policy.py"),
)
is_prerelease = cast(Callable[[str, str], bool], MODULE["is_prerelease"])
verify_main_ancestry = cast(Callable[[Path, str], None], MODULE["verify_main_ancestry"])
verify_merged_prs = cast(Callable[[object, str], None], MODULE["verify_merged_prs"])


@pytest.mark.parametrize(
    "version,preview",
    [("0.1.0", True), ("1.0.0", False), ("1.0.0rc1", True)],
)
def test_release_classification(version: str, preview: bool) -> None:
    assert is_prerelease(f"v{version}", version) is preview


@pytest.mark.parametrize("tag,version", [("v0.2.0", "0.1.0"), ("v1.0.0", "invalid")])
def test_bad_release_version_is_rejected(tag: str, version: str) -> None:
    with pytest.raises(ValueError, match="project.version"):
        is_prerelease(tag, version)


@pytest.mark.parametrize("change", ["none", "unmerged", "other-base", "other-repo", "malformed"])
def test_release_requires_a_merged_pr_for_this_main(change: str) -> None:
    pr: dict[str, object] = {
        "merged_at": "2026-10-18T00:00:00Z",
        "base": {"ref": "main", "repo": {"full_name": "owner/project"}},
    }
    if change == "unmerged":
        pr["merged_at"] = None
    elif change == "other-base":
        pr["base"] = {"ref": "other", "repo": {"full_name": "owner/project"}}
    elif change == "other-repo":
        pr["base"] = {"ref": "main", "repo": {"full_name": "someone/project"}}
    value: object = None if change == "malformed" else [pr]
    if change == "none":
        verify_merged_prs(value, "owner/project")
    else:
        with pytest.raises(ValueError):
            verify_merged_prs(value, "owner/project")


def test_main_ancestry_accepts_merged_history_and_rejects_feature_only_commits() -> None:
    with TemporaryDirectory(dir=".tmp") as directory:
        root = Path(directory).resolve()

        def git(*arguments: str) -> str:
            return subprocess.check_output(
                ["git", *arguments],
                cwd=root,
                text=True,
                stderr=subprocess.STDOUT,
                timeout=30,
            ).strip()

        git("init", "--initial-branch=main")
        git("config", "user.name", "Release Test")
        git("config", "user.email", "release@example.invalid")
        git("commit", "--allow-empty", "-m", "Synthetic main")
        main = git("rev-parse", "HEAD")
        git("update-ref", "refs/remotes/origin/main", main)
        verify_main_ancestry(root, main)
        git("switch", "-c", "feature")
        git("commit", "--allow-empty", "-m", "Synthetic unmerged change")
        with pytest.raises(subprocess.CalledProcessError):
            verify_main_ancestry(root, git("rev-parse", "HEAD"))
        with pytest.raises(ValueError, match="SHA"):
            verify_main_ancestry(root, "--help")
