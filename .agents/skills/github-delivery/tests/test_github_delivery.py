"""Exercise delivery guards using isolated Git repos and simulated GitHub transport."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol, cast

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / ".agents/skills/github-delivery/scripts/git_delivery.py"


class Helper(Protocol):
    def command(self, args: list[str], accepted: tuple[int, ...] = (0,)) -> str: ...
    def git(self, *args: str, accepted: tuple[int, ...] = (0,)) -> str: ...
    def gh(self, *args: str, accepted: tuple[int, ...] = (0,)) -> object: ...
    def fingerprint(self) -> str: ...
    def staged_paths(self) -> list[str]: ...
    def pr(self, request: dict[str, object], expected: bool = True) -> dict[str, object]: ...
    def perform(
        self,
        action: str,
        request: dict[str, object],
        authorized: bool = False,
    ) -> dict[str, object]: ...


class Skill(Protocol):
    Delivery: Callable[[Path], Helper]
    DeliveryError: type[RuntimeError]


spec = importlib.util.spec_from_file_location("github_delivery_skill", SCRIPT)
assert spec is not None and spec.loader is not None
loaded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loaded)
skill = cast(Skill, cast(object, loaded))


@pytest.fixture(scope="module")
def seed_checkout() -> Iterator[Path]:
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="delivery-seed-", dir=ROOT / ".tmp") as directory:
        root = Path(directory) / "checkout with spaces"
        root.mkdir()
        helper = skill.Delivery(root)
        helper.git("init", "--initial-branch=base")
        helper.git("config", "user.name", "Delivery Test")
        helper.git("config", "user.email", "delivery-test@example.invalid")
        helper.git("config", "core.autocrlf", "false")
        (root / ".gitignore").write_text(".tmp/\n", encoding="utf-8")
        (root / ".github").mkdir()
        (root / ".github/commit-message-instructions.md").write_bytes(
            (ROOT / ".github/commit-message-instructions.md").read_bytes(),
        )
        (root / "seed.py").write_text("VALUE = 0\n", encoding="utf-8")
        helper.git("add", "--", ".gitignore", ".github/commit-message-instructions.md", "seed.py")
        helper.git("commit", "-m", "Synthetic baseline")
        helper.git("branch", "main")
        helper.git("switch", "-c", "feature/delivery")
        (root / ".tmp").mkdir()
        yield root


@pytest.fixture
def checkout(seed_checkout: Path) -> Iterator[tuple[Path, Helper, dict[str, object]]]:
    with tempfile.TemporaryDirectory(prefix="delivery-test-", dir=ROOT / ".tmp") as directory:
        container = Path(directory)
        root = container / "checkout with spaces"
        shutil.copytree(seed_checkout, root)
        helper = skill.Delivery(root)
        remote = container / "origin.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        helper.git("remote", "add", "origin", str(remote))
        request: dict[str, object] = {
            "branch": "feature/delivery",
            "head": helper.git("rev-parse", "HEAD").strip(),
            "remote_url": str(remote),
        }
        yield root, helper, request


def operation_file(root: Path, name: str, value: object) -> str:
    filename = root / ".tmp" / name
    filename.write_text(json.dumps(value), encoding="utf-8")
    return f".tmp/{name}"


def message_file(root: Path, message: str) -> str:
    (root / ".tmp/message.txt").write_text(message, encoding="utf-8")
    return ".tmp/message.txt"


@pytest.mark.parametrize("action", ["stage", "commit", "push", "draft-pr", "merge-pr", "sync-main"])
def test_mutations_require_operation_authorization(
    checkout: tuple[Path, Helper, dict[str, object]],
    action: str,
) -> None:
    _, helper, request = checkout
    with pytest.raises(skill.DeliveryError, match="authorization"):
        helper.perform(action, request)
    assert helper.git("rev-parse", "HEAD").strip() == request["head"]
    assert helper.staged_paths() == []


@pytest.mark.parametrize(
    "header",
    [
        ":sparkles: feat(imports): validate imports",
        ":bug: fix(imports): correct validation",
        ":recycle: refactor(imports): simplify parsing",
        ":zap: perf(imports): reduce allocations",
        ":test_tube: test(tests): verify guards",
        ":memo: docs(docs): describe contracts",
        ":package: build(deps): update dependencies",
        ":gear: ci(ci): verify delivery",
        ":wrench: chore(tooling): maintain tools",
    ],
)
def test_commit_policy_accepts_each_documented_type(
    checkout: tuple[Path, Helper, dict[str, object]],
    header: str,
) -> None:
    root, helper, _ = checkout
    result = helper.perform("validate-message", {"message_file": message_file(root, header + "\n")})
    assert result == {"valid": True, "semantic_review_required": True}


@pytest.mark.parametrize(
    "message",
    [
        ":bug: feat(imports): validate imports\n",
        ":memo: docs(Docs): describe contracts\n",
        ":memo: docs(docs): Describe contracts\n",
        ":memo: docs(docs): describe contracts.\n",
        ":memo: docs(docs): " + "a" * 80 + "\n",
        ":memo: docs(docs): describe contracts\nWhy:\nChanges:\n",
        ":memo: docs(docs): describe contracts\n\nChanges:\nWhy:\n",
        ":memo: docs(docs): describe contracts\n\nInvented body\n",
        ":memo: docs(docs): describe contracts\n\nWhy:\nChanges:\n- Describe tests.\n",
        ":memo: docs(docs): describe contracts\n\nWhy:\nProtect scope.\nChanges:\nRefs: M2\n",
    ],
)
def test_invalid_title_or_body_cannot_pass_validation(
    checkout: tuple[Path, Helper, dict[str, object]],
    message: str,
) -> None:
    root, helper, _ = checkout
    with pytest.raises(skill.DeliveryError):
        helper.perform("validate-message", {"message_file": message_file(root, message)})


def test_stage_commit_and_push_preserve_unrelated_work_and_exact_message(
    checkout: tuple[Path, Helper, dict[str, object]],
) -> None:
    root, helper, request = checkout
    filename = "approved file.py"
    (root / filename).write_text("VALUE = 1\n", encoding="utf-8")
    (root / "seed.py").write_text("OWNER_CHANGE = 2\n", encoding="utf-8")
    scope = operation_file(root, "scope.json", [filename])
    staged = helper.perform("stage", {**request, "scope_file": scope}, authorized=True)
    message = ":test_tube: test(tests): verify delivery guards\n\nWhy:\nProtect reviewed scope.\n\nChanges:\n- Add a synthetic test.\n\nRefs: M2\n"
    committed = helper.perform(
        "commit",
        {
            **request,
            "scope_file": scope,
            "fingerprint": staged["fingerprint"],
            "message_file": message_file(root, message),
        },
        authorized=True,
    )
    assert helper.git("show", "--format=", "--name-only", "HEAD").strip() == filename
    assert helper.git("log", "-1", "--format=%B").rstrip() == message.rstrip()
    assert (root / "seed.py").read_text(encoding="utf-8") == "OWNER_CHANGE = 2\n"
    pushed = helper.perform("push", {**request, "head": committed["head"]}, authorized=True)
    assert pushed["head"] == committed["head"]
    assert "refs/heads/feature/delivery" in helper.git("ls-remote", "origin")
    assert "refs/heads/main" not in helper.git("ls-remote", "origin")


def test_reviewed_index_and_changed_fingerprint_block_mutations(
    checkout: tuple[Path, Helper, dict[str, object]],
) -> None:
    root, helper, request = checkout
    (root / "approved.py").write_text("VALUE = 1\n", encoding="utf-8")
    scope = operation_file(root, "scope.json", ["approved.py"])
    staged = helper.perform("stage", {**request, "scope_file": scope}, authorized=True)
    with pytest.raises(skill.DeliveryError, match="owner-reviewed"):
        helper.perform("stage", {**request, "scope_file": scope}, authorized=True)
    (root / "approved.py").write_text("VALUE = 2\n", encoding="utf-8")
    helper.git("add", "--", "approved.py")
    with pytest.raises(skill.DeliveryError, match="changed after review"):
        helper.perform(
            "commit",
            {
                **request,
                "scope_file": scope,
                "fingerprint": staged["fingerprint"],
                "message_file": message_file(root, ":test_tube: test(tests): verify guards\n"),
            },
            authorized=True,
        )
    assert helper.staged_paths() == ["approved.py"]
    assert helper.git("rev-parse", "HEAD").strip() == request["head"]


@pytest.mark.parametrize(
    "scope",
    [["../outside.py"], [".tmp/message.txt"], [".git/config"], ["seed.py", "seed.py"], [".github"]],
)
def test_invalid_scope_leaves_index_empty(
    checkout: tuple[Path, Helper, dict[str, object]],
    scope: list[str],
) -> None:
    root, helper, request = checkout
    with pytest.raises(skill.DeliveryError):
        helper.perform(
            "stage",
            {**request, "scope_file": operation_file(root, "scope.json", scope)},
            authorized=True,
        )
    assert helper.staged_paths() == []


@pytest.mark.parametrize("change", ["main", "detached", "wrong-head", "wrong-origin"])
def test_push_guards_reject_protected_or_changed_context(
    checkout: tuple[Path, Helper, dict[str, object]],
    change: str,
) -> None:
    _, helper, request = checkout
    if change == "main":
        helper.git("switch", "main")
        request["branch"] = "main"
    elif change == "detached":
        helper.git("switch", "--detach")
    elif change == "wrong-head":
        request["head"] = "f" * 40
    else:
        request["remote_url"] = "unexpected"
    with pytest.raises(skill.DeliveryError):
        helper.perform("push", request, authorized=True)


def github_transport(
    root: Path,
    helper: Helper,
    request: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    *,
    bucket: str = "pass",
    moved: bool = False,
    existing: bool = False,
) -> list[list[str]]:
    helper.git("remote", "set-url", "origin", "https://github.com/owner/ride.git")
    request.update(repository="owner/ride", remote_url="https://github.com/owner/ride.git", pr=9)
    message_file(root, "PR body\n")
    request.update(title="Review delivery", body_file=".tmp/message.txt")
    calls: list[list[str]] = []
    state: dict[str, object] = {
        "number": 9,
        "html_url": "https://github.com/owner/ride/pull/9",
        "state": "open",
        "draft": False,
        "merged": False,
        "merge_commit_sha": None,
        "base": {"ref": "main"},
        "head": {
            "ref": request["branch"],
            "sha": request["head"],
            "repo": {"full_name": "owner/ride"},
        },
    }
    reads = 0

    def gh(*args: str, accepted: tuple[int, ...] = (0,)) -> object:
        nonlocal reads
        calls.append(list(args))
        if args[:2] == ("pr", "checks"):
            return [{"name": "check", "workflow": "CI", "state": "SUCCESS", "bucket": bucket}]
        if "--input" in args:
            payload = json.loads(Path(args[args.index("--input") + 1]).read_text(encoding="utf-8"))
            if args[1].endswith("/merge"):
                assert payload["sha"] == request["head"]
                state.update(merged=True, state="closed", merge_commit_sha="a" * 40)
                return {"merged": True, "sha": "a" * 40}
            assert payload["base"] == "main" and payload["draft"] is True
            state["draft"] = True
            return state
        if args[1].endswith("/pulls"):
            return [state] if existing else []
        reads += 1
        if moved and reads > 1:
            state["head"] = {
                "ref": request["branch"],
                "sha": "f" * 40,
                "repo": {"full_name": "owner/ride"},
            }
        return state

    real_git = helper.git

    def git(*args: str, accepted: tuple[int, ...] = (0,)) -> str:
        if args[0] == "ls-remote":
            return f"{request['head']}\trefs/heads/{request['branch']}\n"
        return real_git(*args, accepted=accepted)

    monkeypatch.setattr(helper, "gh", gh)
    monkeypatch.setattr(helper, "git", git)
    return calls


@pytest.mark.parametrize("bucket", ["pending", "fail", "cancel", "skipping", "unknown"])
def test_merge_never_runs_when_final_check_is_not_successful(
    checkout: tuple[Path, Helper, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
    bucket: str,
) -> None:
    root, helper, request = checkout
    calls = github_transport(root, helper, request, monkeypatch, bucket=bucket)
    with pytest.raises(skill.DeliveryError, match="not green"):
        helper.perform("merge-pr", request, authorized=True)
    assert all("--input" not in call for call in calls)


def test_changed_pr_sha_blocks_merge_after_check_read(
    checkout: tuple[Path, Helper, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, helper, request = checkout
    calls = github_transport(root, helper, request, monkeypatch, moved=True)
    with pytest.raises(skill.DeliveryError, match="head changed"):
        helper.perform("merge-pr", request, authorized=True)
    assert all("--input" not in call for call in calls)


@pytest.mark.parametrize("existing", [False, True])
def test_draft_creation_is_verified_and_existing_pr_is_reused(
    checkout: tuple[Path, Helper, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
) -> None:
    root, helper, request = checkout
    calls = github_transport(root, helper, request, monkeypatch, existing=existing)
    result = helper.perform("draft-pr", request, authorized=True)
    assert result["existing"] is existing
    assert result["draft"] is (not existing)
    assert sum("--input" in call for call in calls) == (0 if existing else 1)


def test_green_merge_uses_expected_sha_and_verifies_remote_result(
    checkout: tuple[Path, Helper, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, helper, request = checkout
    calls = github_transport(root, helper, request, monkeypatch)
    result = helper.perform("merge-pr", request, authorized=True)
    assert result["merged"] is True
    assert result["merge_sha"] == "a" * 40
    assert sum("--input" in call for call in calls) == 1


def test_sync_never_stashes_or_overwrites_owner_changes(
    checkout: tuple[Path, Helper, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, helper, request = checkout
    calls = github_transport(root, helper, request, monkeypatch)
    helper.perform("merge-pr", request, authorized=True)
    (root / "seed.py").write_text("OWNER_CHANGE = 1\n", encoding="utf-8")
    with pytest.raises(skill.DeliveryError, match="clean checkout"):
        helper.perform("sync-main", {**request, "merge_sha": "a" * 40}, authorized=True)
    assert (root / "seed.py").read_text(encoding="utf-8") == "OWNER_CHANGE = 1\n"
    assert helper.git("branch", "--show-current").strip() == "feature/delivery"
    assert sum("--input" in call for call in calls) == 1


def test_push_does_not_publish_tags_enabled_in_user_configuration(
    checkout: tuple[Path, Helper, dict[str, object]],
) -> None:
    _, helper, request = checkout
    helper.git("config", "push.followTags", "true")
    helper.git("tag", "-a", "owner-tag", "-m", "Synthetic annotation")
    helper.perform("push", request, authorized=True)
    assert "refs/tags/" not in helper.git("ls-remote", "origin")


def test_mirror_boolean_is_rejected_before_push(
    checkout: tuple[Path, Helper, dict[str, object]],
) -> None:
    _, helper, request = checkout
    helper.git("config", "remote.origin.mirror", "TRUE")
    with pytest.raises(skill.DeliveryError, match="Mirror"):
        helper.perform("push", request, authorized=True)


def test_commit_hook_message_change_is_reported_without_automatic_rollback(
    checkout: tuple[Path, Helper, dict[str, object]],
) -> None:
    root, helper, request = checkout
    (root / "approved.py").write_text("VALUE = 1\n", encoding="utf-8")
    scope = operation_file(root, "scope.json", ["approved.py"])
    staged = helper.perform("stage", {**request, "scope_file": scope}, authorized=True)
    hook = root / ".git/hooks/commit-msg"
    hook.write_text('#!/bin/sh\nprintf "changed by hook\\n" > "$1"\n', encoding="utf-8")
    hook.chmod(0o755)
    with pytest.raises(skill.DeliveryError, match="Commit occurred.*message"):
        helper.perform(
            "commit",
            {
                **request,
                "scope_file": scope,
                "fingerprint": staged["fingerprint"],
                "message_file": message_file(root, ":test_tube: test(tests): verify guards\n"),
            },
            authorized=True,
        )
    assert helper.git("rev-parse", "HEAD").strip() != request["head"]
    assert helper.git("log", "-1", "--format=%B").strip() == "changed by hook"


def test_clean_sync_only_fast_forwards_to_the_verified_remote_merge(
    checkout: tuple[Path, Helper, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, helper, request = checkout
    (root / "approved.py").write_text("VALUE = 1\n", encoding="utf-8")
    scope = operation_file(root, "scope.json", ["approved.py"])
    staged = helper.perform("stage", {**request, "scope_file": scope}, authorized=True)
    committed = helper.perform(
        "commit",
        {
            **request,
            "scope_file": scope,
            "fingerprint": staged["fingerprint"],
            "message_file": message_file(root, ":test_tube: test(tests): verify guards\n"),
        },
        authorized=True,
    )
    # Simulate GitHub's already-authorized remote merge in the isolated bare repo.
    helper.git("push", "origin", "HEAD:refs/heads/main")

    def merged_pr(values: dict[str, object], expected: bool = True) -> dict[str, object]:
        assert values["head"] == committed["head"]
        return {"merged": True, "merge_commit_sha": committed["head"]}

    monkeypatch.setattr(helper, "pr", merged_pr)
    result = helper.perform(
        "sync-main",
        {
            **request,
            "head": committed["head"],
            "merge_sha": committed["head"],
        },
        authorized=True,
    )
    assert result == {"branch": "main", "head": committed["head"]}
    assert helper.git("status", "--porcelain") == ""


def test_nested_root_and_operation_files_outside_tmp_are_rejected(
    checkout: tuple[Path, Helper, dict[str, object]],
) -> None:
    root, helper, request = checkout
    nested = root / "nested"
    nested.mkdir()
    with pytest.raises(skill.DeliveryError, match="exact repository root"):
        skill.Delivery(nested).perform("inspect", {})
    with pytest.raises(skill.DeliveryError, match=".tmp"):
        helper.perform("validate-message", {"message_file": "seed.py"})
    helper.git("remote", "set-url", "origin", "https://secret@example.invalid/repo.git")
    with pytest.raises(skill.DeliveryError, match="Credential-bearing"):
        helper.perform("inspect", {})
    assert helper.git("rev-parse", "HEAD").strip() == request["head"]


def test_windows_cli_reports_review_state_without_mutating_index(
    checkout: tuple[Path, Helper, dict[str, object]],
) -> None:
    root, helper, request = checkout
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "inspect", "--root", str(root)],
        capture_output=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["head"] == request["head"]
    assert report["staged"] == []
    assert helper.staged_paths() == []


def test_push_uses_reviewed_sha_when_head_moves_at_transport_boundary(
    checkout: tuple[Path, Helper, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, helper, request = checkout
    original = helper.git

    def concurrent_git(*args: str, accepted: tuple[int, ...] = (0,)) -> str:
        if "push" in args:
            original("commit", "--allow-empty", "-m", "Synthetic concurrent owner change")
        return original(*args, accepted=accepted)

    monkeypatch.setattr(helper, "git", concurrent_git)
    result = helper.perform("push", request, authorized=True)
    assert result["head"] == request["head"]
    assert original("rev-parse", "HEAD").strip() != request["head"]
    assert (
        original("ls-remote", "origin", "refs/heads/feature/delivery").split()[0] == request["head"]
    )
