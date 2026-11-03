"""Release policy requires reviewed main history and explicit version classification."""

from collections.abc import Callable
from pathlib import Path
import runpy
import json
import subprocess
from tempfile import TemporaryDirectory
from typing import cast

import pytest

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / ".github/scripts/check-release-policy.py"),
)
is_prerelease = cast(Callable[[str, str], bool], MODULE["is_prerelease"])
verify_main_ancestry = cast(Callable[[Path, str], None], MODULE["verify_main_ancestry"])
verify_merged_prs = cast(Callable[[object, str], None], MODULE["verify_merged_prs"])
reusable_application_checks = cast(
    Callable[[Path, str, str, object], bool],
    MODULE["reusable_application_checks"],
)


@pytest.mark.parametrize(
    "version,preview",
    [("0.1.0", True), ("2.0.0", False), ("1.1.0rc1", True)],
)
def test_release_classification(version: str, preview: bool) -> None:
    assert is_prerelease(f"v{version}", version) is preview


@pytest.mark.parametrize("tag,version", [("v0.3.1", "0.1.0"), ("v1.1.0", "invalid")])
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


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "no-image",
        "changed-workflow-revision",
        "no-pr",
        "unmerged",
        "wrong-base",
        "bad-head",
        "changed-tree",
        "missing-tree",
        "no-run",
        "failed-run",
        "running-run",
        "wrong-workflow",
        "wrong-head",
        "wrong-event",
        "foreign-repository",
        "missing-job",
        "duplicate-job",
        "skipped-job",
        "failed-job",
        "pending-job",
        "changed-image",
        "missing-image",
        "missing-tested-tree",
        "wrong-tested-tree",
        "api-error",
    ],
)
def test_application_reuse_requires_complete_matching_hosted_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    head, commit, tree = "a" * 40, "b" * 40, "c" * 40
    monkeypatch.setenv("ImageVersion", "20261101.1")
    monkeypatch.setenv("GITHUB_WORKFLOW_SHA", commit)
    pr: dict[str, object] = {
        "number": 1,
        "merged_at": "2026-11-01",
        "head": {"sha": head},
        "base": {"ref": "main", "repo": {"full_name": "owner/project"}},
    }
    run: dict[str, object] = {
        "id": 2,
        "head_sha": head,
        "event": "pull_request",
        "path": ".github/workflows/ci.yml",
        "head_repository": {"full_name": "owner/project"},
        "status": "completed",
        "conclusion": "success",
    }
    jobs = [
        {"name": name, "id": index, "status": "completed", "conclusion": "success"}
        for index, name in enumerate(
            ("check", "Application quality and tests", "User interface and screenshots"),
        )
    ]
    log = f"Image: windows-2025\nVersion: 20261101.1\nTested tree: {tree}\n"
    if change == "no-image":
        monkeypatch.setenv("ImageVersion", "")
    elif change == "changed-workflow-revision":
        monkeypatch.setenv("GITHUB_WORKFLOW_SHA", "d" * 40)
    elif change == "unmerged":
        pr["merged_at"] = None
    elif change == "wrong-base":
        pr["base"] = {"ref": "other", "repo": {"full_name": "owner/project"}}
    elif change == "bad-head":
        pr["head"] = {"sha": "--all"}
    elif change == "failed-run":
        run["conclusion"] = "failure"
    elif change == "running-run":
        run["status"] = "in_progress"
    elif change == "wrong-workflow":
        run["path"] = ".github/workflows/other.yml"
    elif change == "wrong-head":
        run["head_sha"] = "d" * 40
    elif change == "wrong-event":
        run["event"] = "push"
    elif change == "foreign-repository":
        run["head_repository"] = {"full_name": "other/project"}
    elif change == "missing-job":
        jobs.pop()
    elif change == "duplicate-job":
        jobs.append(jobs[-1].copy())
    elif change in {"skipped-job", "failed-job"}:
        jobs[-1]["conclusion"] = "skipped" if change == "skipped-job" else "failure"
    elif change == "pending-job":
        jobs[-1]["status"] = "in_progress"
    elif change == "changed-image":
        log = log.replace("20261101.1", "20261102.1")
    elif change == "missing-image":
        log = f"Tested tree: {tree}\n"
    elif change == "missing-tested-tree":
        log = log.split("Tested tree:")[0]
    elif change == "wrong-tested-tree":
        log = log.replace(tree, "d" * 40)

    calls: list[list[str]] = []

    def output(command: list[str], **_kwargs: object) -> str:
        calls.append(command)
        if command[0] == "git":
            assert command == ["git", "rev-parse", f"{commit}^{{tree}}", f"{head}^{{tree}}"]
            if change == "missing-tree":
                raise subprocess.CalledProcessError(1, command)
            return f"{tree}\n{'d' * 40 if change == 'changed-tree' else tree}\n"
        assert command[:2] == ["gh", "api"]
        if change == "api-error":
            raise subprocess.CalledProcessError(1, command)
        if "/workflows/ci.yml/runs?" in command[-1]:
            assert command[-1].endswith(f"event=pull_request&head_sha={head}&per_page=1")
            return json.dumps({"workflow_runs": [] if change == "no-run" else [run]})
        if command[-1].endswith("/jobs?filter=latest&per_page=100"):
            return json.dumps({"jobs": jobs})
        assert command[-1].endswith("/logs")
        return log

    monkeypatch.setattr(subprocess, "check_output", output)
    assert reusable_application_checks(
        tmp_path,
        commit,
        "owner/project",
        [] if change == "no-pr" else [pr],
    ) is (change == "none")
    if change == "no-image":
        assert calls == []
