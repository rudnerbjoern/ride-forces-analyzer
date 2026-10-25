"""Guarded Windows Git/GitHub delivery; authorization remains the owner's decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import cast


class DeliveryError(RuntimeError):
    """An operation cannot proceed with the reviewed inputs."""


def mapping(value: object) -> dict[str, object]:
    """Require a mapping-shaped operation or GitHub response value.

    Args:
        value: Candidate value to validate, format or store.

    Returns:
        The validated mapping, preserving its field values.

    Raises:
        DeliveryError: Expected a JSON object.
    """
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise DeliveryError("Expected a JSON object.")
    return cast(dict[str, object], value)


def text_field(value: dict[str, object], name: str) -> str:
    """Read a required nonempty textual operation field.

    Args:
        value: Candidate value to validate, format or store.
        name: Display name or identifier used to select the requested item.

    Returns:
        The required nonempty field value.

    Raises:
        DeliveryError: If the supplied settings or operation state are invalid.
    """
    item = value.get(name)
    if not isinstance(item, str) or not item:
        raise DeliveryError(f"Missing string field: {name}.")
    return item


def sha(value: str) -> str:
    """Validate and return a full hexadecimal commit identity.

    Args:
        value: Candidate value to validate, format or store.

    Returns:
        The validated full commit identity.

    Raises:
        DeliveryError: Expected a full commit SHA.
    """
    if not re.fullmatch(r"[a-f0-9]{40}", value):
        raise DeliveryError("Expected a full commit SHA.")
    return value


class Delivery:
    """Delivery contract and owned data.

    Attributes:
        root: Checkout or data root used to resolve the operation's paths.
    """

    def __init__(self, root: Path) -> None:
        """Initialize delivery and its owned state.

        Args:
            root: Checkout or data root used to resolve the operation's paths.

        Returns:
            None.
        """
        self.root = root.resolve()

    def command(self, args: list[str], accepted: tuple[int, ...] = (0,)) -> str:
        """Run a bounded native command and require an admitted exit status.

        Args:
            args: Command and arguments passed to the subprocess.
            accepted: Process exit statuses admitted as successful.

        Returns:
            Captured standard output from the successful command.

        Raises:
            DeliveryError: If the supplied settings or operation state are invalid.
        """
        result = subprocess.run(
            args,
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            timeout=90,
            check=False,
        )
        if result.returncode not in accepted:
            raise DeliveryError(f"{args[0]} failed: {result.stderr.strip()}")
        return result.stdout

    def git(self, *args: str, accepted: tuple[int, ...] = (0,)) -> str:
        """Run Git inside the selected checkout.

        Args:
            accepted: Process exit statuses admitted as successful.
            *args: Additional positional arguments accepted by the callback.

        Returns:
            Captured standard output from Git.
        """
        return self.command(["git", "--literal-pathspecs", "-C", str(self.root), *args], accepted)

    def gh(self, *args: str, accepted: tuple[int, ...] = (0,)) -> object:
        """Run the GitHub CLI and decode its JSON response.

        Args:
            accepted: Process exit statuses admitted as successful.
            *args: Additional positional arguments accepted by the callback.

        Returns:
            The decoded GitHub CLI JSON response.

        Raises:
            DeliveryError: GitHub returned no valid JSON; inspect state before retrying.
        """
        output = self.command(["gh", *args], accepted)
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise DeliveryError(
                "GitHub returned no valid JSON; inspect state before retrying.",
            ) from error

    def temporary_file(self, filename: str) -> Path:
        """Resolve an existing operation file confined to the checkout's temporary area.

        Args:
            filename: Name of the requested input or output file.

        Returns:
            The existing file path inside the checkout temporary directory.

        Raises:
            DeliveryError: Operation files must be inside repository .tmp/. Operation file
                does not exist.
        """
        candidate = (self.root / filename).resolve()
        temporary = (self.root / ".tmp").resolve()
        if not temporary.is_relative_to(self.root) or not candidate.is_relative_to(temporary):
            raise DeliveryError("Operation files must be inside repository .tmp/.")
        if not candidate.is_file():
            raise DeliveryError("Operation file does not exist.")
        return candidate

    def staged_paths(self) -> list[str]:
        """Return the exact paths currently staged for commit.

        Returns:
            The exact paths currently staged for commit.
        """
        return [
            name for name in self.git("diff", "--cached", "--name-only", "-z").split("\0") if name
        ]

    def fingerprint(self) -> str:
        """Hash the staged diff used to guard reviewed commit contents.

        Returns:
            SHA-256 digest of the staged diff.
        """
        raw = self.git("diff", "--cached", "--raw", "--abbrev=40", "-z")
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def remote_url(self) -> str:
        """Read the checkout's origin URL.

        Returns:
            The configured origin URL.

        Raises:
            DeliveryError: Origin must have exactly one push URL. Mirror remotes are
                prohibited. Credential-bearing remote URLs are not supported.
        """
        urls = self.git("remote", "get-url", "--push", "--all", "origin").splitlines()
        if len(urls) != 1:
            raise DeliveryError("Origin must have exactly one push URL.")
        if (
            self.git("config", "--bool", "--get", "remote.origin.mirror", accepted=(0, 1)).strip()
            == "true"
        ):
            raise DeliveryError("Mirror remotes are prohibited.")
        if re.match(r"https?://[^/]*@", urls[0]):
            raise DeliveryError("Credential-bearing remote URLs are not supported.")
        return urls[0]

    def branch_guard(self, request: dict[str, object]) -> str:
        """Require the reviewed dedicated branch and local head identity.

        Args:
            request: Request carrying the inputs and context for this operation.

        Returns:
            The verified active branch name.

        Raises:
            DeliveryError: An authorized feature branch is required. Active branch does not
                match the reviewed feature branch. HEAD changed after review.
        """
        branch = text_field(request, "branch")
        if branch == "main" or branch.startswith("-"):
            raise DeliveryError("An authorized feature branch is required.")
        self.git("check-ref-format", "--branch", branch)
        if self.git("branch", "--show-current").strip() != branch:
            raise DeliveryError("Active branch does not match the reviewed feature branch.")
        if self.git("rev-parse", "HEAD").strip() != sha(text_field(request, "head")):
            raise DeliveryError("HEAD changed after review.")
        return branch

    def remote_guard(self, request: dict[str, object]) -> None:
        """Require the reviewed origin and safe explicit publication configuration.

        Args:
            request: Request carrying the inputs and context for this operation.

        Returns:
            None.

        Raises:
            DeliveryError: Origin URL changed after review.
        """
        if self.remote_url() != text_field(request, "remote_url"):
            raise DeliveryError("Origin URL changed after review.")

    def scope(self, request: dict[str, object]) -> list[str]:
        """Read and validate the exact authorized staged-file scope.

        Args:
            request: Request carrying the inputs and context for this operation.

        Returns:
            The exact authorized staged paths.

        Raises:
            OSError: If the required filesystem operation fails.
            DeliveryError: A nonempty exact path array is required. Use exact
                repository-relative paths with forward slashes. Invalid approved path.
                Approved scope contains duplicate paths.
        """
        value: object = json.loads(
            self.temporary_file(text_field(request, "scope_file")).read_text(encoding="utf-8"),
        )
        if not isinstance(value, list) or not value:
            raise DeliveryError("A nonempty exact path array is required.")
        paths: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item or "\\" in item:
                raise DeliveryError("Use exact repository-relative paths with forward slashes.")
            parts = item.split("/")
            if (
                any(part in {"", ".", ".."} for part in parts)
                or parts[0] in {".git", ".tmp"}
                or ":" in item
                or any(ord(character) < 32 for character in item)
            ):
                raise DeliveryError("Invalid approved path.")
            paths.append(item)
        if len(set(paths)) != len(paths):
            raise DeliveryError("Approved scope contains duplicate paths.")
        return paths

    def validate_message(self, filename: str) -> str:
        """Validate commit or PR title mechanics against the repository policy.

        Args:
            filename: Name of the requested input or output file.

        Returns:
            The message after mechanical title validation.

        Raises:
            OSError: If the required filesystem operation fails.
            DeliveryError: Empty commit message. Commit title violates the project policy.
                Separate title and body with a blank line. A substantive body requires Why:
                followed by Changes:. Why: and Changes: must include substantive text.
        """
        message = self.temporary_file(filename).read_text(encoding="utf-8")
        lines = message.splitlines()
        if not lines:
            raise DeliveryError("Empty commit message.")
        policy = (self.root / ".github/commit-message-instructions.md").read_text(encoding="utf-8")
        icons = dict(re.findall(r"^\s*- `(:[a-z_]+:) ([a-z]+)`$", policy, re.MULTILINE))
        match = re.fullmatch(r"(:[a-z_]+:) ([a-z]+)\(([a-z][a-z0-9-]*)\): ([a-z].*)", lines[0])
        if (
            match is None
            or len(lines[0]) > 80
            or lines[0].endswith(".")
            or icons.get(match[1]) != match[2]
        ):
            raise DeliveryError("Commit title violates the project policy.")
        body = [line for line in lines[1:] if line.strip()]
        if body:
            if lines[1] != "":
                raise DeliveryError("Separate title and body with a blank line.")
            footers_only = all(re.match(r"^(Refs|Fixes): .+", line) for line in body)
            if not footers_only and (
                "Why:" not in body
                or "Changes:" not in body
                or body.index("Why:") >= body.index("Changes:")
            ):
                raise DeliveryError("A substantive body requires Why: followed by Changes:.")
            if not footers_only:
                reason = body[body.index("Why:") + 1 : body.index("Changes:")]
                effects = body[body.index("Changes:") + 1 :]
                if not reason or not any(
                    not re.match(r"^(Refs|Fixes|Validation|BREAKING CHANGE):", line)
                    for line in effects
                ):
                    raise DeliveryError("Why: and Changes: must include substantive text.")
        return message

    def repository(self, request: dict[str, object]) -> str:
        """Require the selected GitHub repository to match the checkout's origin.

        Args:
            request: Request carrying the inputs and context for this operation.

        Returns:
            The verified GitHub repository name.

        Raises:
            DeliveryError: Invalid GitHub repository name. GitHub repository does not match
                origin.
        """
        self.remote_guard(request)
        repository = text_field(request, "repository")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise DeliveryError("Invalid GitHub repository name.")
        url = self.remote_url()
        if url not in {
            f"https://github.com/{repository}.git",
            f"https://github.com/{repository}",
            f"git@github.com:{repository}.git",
        }:
            raise DeliveryError("GitHub repository does not match origin.")
        return repository

    def pr(self, request: dict[str, object], expected: bool = True) -> dict[str, object]:
        """Read and verify the selected pull request's repository, base and head.

        Args:
            request: Request carrying the inputs and context for this operation.
            expected: Whether to enforce the reviewed remote head identity.

        Returns:
            Pull request metadata with a verified base and head.

        Raises:
            DeliveryError: A positive PR number is required. PR must target main. PR head must
                belong to the selected repository. PR head changed after review.
        """
        repository = self.repository(request)
        number = request.get("pr")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise DeliveryError("A positive PR number is required.")
        value = mapping(self.gh("api", f"repos/{repository}/pulls/{number}"))
        if mapping(value["base"]).get("ref") != "main":
            raise DeliveryError("PR must target main.")
        if mapping(mapping(value["head"])["repo"]).get("full_name") != repository:
            raise DeliveryError("PR head must belong to the selected repository.")
        if expected and (
            mapping(value["head"]).get("sha") != sha(text_field(request, "head"))
            or mapping(value["head"]).get("ref") != text_field(request, "branch")
        ):
            raise DeliveryError("PR head changed after review.")
        return value

    def checks(self, request: dict[str, object]) -> dict[str, object]:
        """Classify the current PR checks and require the final CI gate for green status.

        Args:
            request: Request carrying the inputs and context for this operation.

        Returns:
            Check states and the resulting merge-gate status.

        Raises:
            DeliveryError: PR is not open for delivery. PR checks are unavailable.
        """
        before = self.pr(request)
        if before.get("state") != "open" or before.get("merged"):
            raise DeliveryError("PR is not open for delivery.")
        rows = self.gh(
            "pr",
            "checks",
            str(request["pr"]),
            "--repo",
            text_field(request, "repository"),
            "--json",
            "name,state,bucket,link,workflow",
            accepted=(0, 1, 8),
        )
        if not isinstance(rows, list):
            raise DeliveryError("PR checks are unavailable.")
        checks = [mapping(row) for row in rows]
        self.pr(request)
        final = [
            row for row in checks if row.get("name") == "check" and row.get("workflow") == "CI"
        ]
        green = (
            len(final) == 1
            and final[0].get("bucket") == "pass"
            and final[0].get("state") == "SUCCESS"
            and all(row.get("bucket") in {"pass", "skipping"} for row in checks)
        )
        status = (
            "green"
            if green
            else "pending"
            if any(row.get("bucket") == "pending" for row in checks)
            else "blocked"
        )
        return {"head": request["head"], "green": green, "status": status, "checks": checks}

    def api_write(
        self,
        endpoint: str,
        method: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        """Send the authorized JSON mutation through the GitHub CLI.

        Args:
            endpoint: Service endpoint to query.
            method: HTTP request method.
            payload: Serialized request body.

        Returns:
            The decoded response to the authorized GitHub mutation.

        Raises:
            DeliveryError: Temporary directory leaves the repository.
            OSError: If the required filesystem operation fails.
        """
        temporary = self.root / ".tmp"
        if not temporary.resolve().is_relative_to(self.root):
            raise DeliveryError("Temporary directory leaves the repository.")
        temporary.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="github-delivery-", dir=temporary) as directory:
            filename = Path(directory) / "request.json"
            filename.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return mapping(self.gh("api", endpoint, "--method", method, "--input", str(filename)))

    def perform(
        self,
        action: str,
        request: dict[str, object],
        authorized: bool = False,
    ) -> dict[str, object]:
        """Dispatch one guarded inspection or explicitly authorized delivery operation.

        Args:
            action: Supported delivery or dialog action to dispatch.
            request: Request carrying the inputs and context for this operation.
            authorized: Whether the owner explicitly authorized this mutation and scope.

        Returns:
            Structured result of the requested operation.

        Raises:
            DeliveryError: Explicit owner authorization is required for this mutation. Select
                the exact repository root. Preserve the owner-reviewed index; it must be empty
                for staging. Approved scope must name files, not directories. Staged scope or
                contents changed after review. Index changed while validating the message.
                Commit occurred but a hook changed its reviewed message. Commit occurred but
                committed contents differ from reviewed index. Staging changed the index but
                scope verification failed; stop for review. Push occurred but remote SHA
                verification failed; inspect remote state. PR branch has not been published at
                the reviewed SHA. Ambiguous existing PR state. PR title must be nonempty and
                contain no control characters. PR is not open for metadata updates. PR draft
                status is unavailable. If the supplied settings or operation state are
                invalid. If the underlying operation fails; the original error is propagated.
                Unsupported PR merge method. Current PR checks are not green. Checks changed
                after draft transition; merge stopped. Merge response requires remote-state
                reconciliation; do not retry blindly. Only an already verified remote PR merge
                may be synchronized. Preserve owner changes; synchronization requires a clean
                checkout. Synchronization completed but final clean-state verification failed.
                Unsupported delivery action.
            OSError: If the required filesystem operation fails.
        """
        if (
            action in {"stage", "commit", "push", "draft-pr", "update-pr", "merge-pr", "sync-main"}
            and not authorized
        ):
            raise DeliveryError("Explicit owner authorization is required for this mutation.")
        if Path(self.git("rev-parse", "--show-toplevel").strip()).resolve() != self.root:
            raise DeliveryError("Select the exact repository root.")
        if action == "inspect":
            return {
                "branch": self.git("branch", "--show-current").strip(),
                "head": self.git("rev-parse", "HEAD").strip(),
                "remote_url": self.remote_url(),
                "staged": self.staged_paths(),
                "fingerprint": self.fingerprint(),
                "status": self.git("status", "--porcelain"),
            }
        if action == "validate-message":
            self.validate_message(text_field(request, "message_file"))
            return {"valid": True, "semantic_review_required": True}
        if action in {"stage", "commit"}:
            paths = self.scope(request)
            self.branch_guard(request)
            if action == "stage":
                if self.staged_paths():
                    raise DeliveryError(
                        "Preserve the owner-reviewed index; it must be empty for staging.",
                    )
                if any((self.root / name).is_dir() for name in paths):
                    raise DeliveryError("Approved scope must name files, not directories.")
                self.git("add", "--", *paths)
            else:
                if set(self.staged_paths()) != set(paths) or self.fingerprint() != text_field(
                    request,
                    "fingerprint",
                ):
                    raise DeliveryError("Staged scope or contents changed after review.")
                message_file = text_field(request, "message_file")
                message = self.validate_message(message_file)
                self.branch_guard(request)
                if self.fingerprint() != request["fingerprint"]:
                    raise DeliveryError("Index changed while validating the message.")
                self.git("commit", "-F", str(self.temporary_file(message_file)))
                if self.git("log", "-1", "--format=%B").rstrip() != message.rstrip():
                    raise DeliveryError("Commit occurred but a hook changed its reviewed message.")
                committed = self.git(
                    "diff",
                    "--raw",
                    "--abbrev=40",
                    "-z",
                    str(request["head"]),
                    "HEAD",
                )
                if hashlib.sha256(committed.encode("utf-8")).hexdigest() != request["fingerprint"]:
                    raise DeliveryError(
                        "Commit occurred but committed contents differ from reviewed index.",
                    )
            if action == "stage" and set(self.staged_paths()) != set(paths):
                raise DeliveryError(
                    "Staging changed the index but scope verification failed; stop for review.",
                )
            return {
                "head": self.git("rev-parse", "HEAD").strip(),
                "staged": self.staged_paths(),
                "fingerprint": self.fingerprint(),
            }
        if action == "push":
            branch = self.branch_guard(request)
            self.remote_guard(request)
            self.branch_guard(request)
            reviewed_head = sha(text_field(request, "head"))
            self.git(
                "-c",
                "push.followTags=false",
                "-c",
                "push.recurseSubmodules=no",
                "push",
                "--set-upstream",
                "origin",
                f"{reviewed_head}:refs/heads/{branch}",
            )
            remote = self.git("ls-remote", "origin", f"refs/heads/{branch}").split()
            if not remote or remote[0] != request["head"]:
                raise DeliveryError(
                    "Push occurred but remote SHA verification failed; inspect remote state.",
                )
            return {"head": remote[0], "branch": branch}
        if action == "pr-info":
            value = self.pr(request, expected=False)
            return {
                key: value.get(key)
                for key in (
                    "number",
                    "title",
                    "body",
                    "html_url",
                    "state",
                    "draft",
                    "merged",
                    "merge_commit_sha",
                    "head",
                    "base",
                )
            }
        if action == "pr-checks":
            return self.checks(request)
        if action == "draft-pr":
            branch = self.branch_guard(request)
            repository = self.repository(request)
            remote = self.git("ls-remote", "origin", f"refs/heads/{branch}").split()
            if not remote or remote[0] != request["head"]:
                raise DeliveryError("PR branch has not been published at the reviewed SHA.")
            existing = self.gh(
                "api",
                f"repos/{repository}/pulls",
                "--method",
                "GET",
                "-f",
                "state=open",
                "-f",
                f"head={repository.split('/')[0]}:{branch}",
            )
            if not isinstance(existing, list) or len(existing) > 1:
                raise DeliveryError("Ambiguous existing PR state.")
            if existing:
                value = mapping(existing[0])
            else:
                value = self.api_write(
                    f"repos/{repository}/pulls",
                    "POST",
                    {
                        "base": "main",
                        "head": branch,
                        "draft": True,
                        "title": text_field(request, "title"),
                        "body": self.temporary_file(text_field(request, "body_file")).read_text(
                            encoding="utf-8",
                        ),
                    },
                )
            checked = self.pr({**request, "pr": value["number"]})
            return {
                "number": checked["number"],
                "url": checked["html_url"],
                "draft": checked["draft"],
                "existing": bool(existing),
            }
        if action == "update-pr":
            self.branch_guard(request)
            repository = self.repository(request)
            title = text_field(request, "title")
            if not title.strip() or any(ord(character) < 32 for character in title):
                raise DeliveryError("PR title must be nonempty and contain no control characters.")
            body = (
                self.temporary_file(text_field(request, "body_file")).read_bytes().decode("utf-8")
            )
            before = self.pr(request)
            draft = before.get("draft")
            if before.get("state") != "open" or before.get("merged") is not False:
                raise DeliveryError("PR is not open for metadata updates.")
            if not isinstance(draft, bool):
                raise DeliveryError("PR draft status is unavailable.")
            previous_body = "" if before.get("body") is None else before["body"]
            updated = before.get("title") != title or previous_body != body
            if updated:
                self.branch_guard(request)
                self.api_write(
                    f"repos/{repository}/pulls/{request['pr']}",
                    "PATCH",
                    {"title": title, "body": body},
                )
            try:
                checked = self.pr(request)
                checked_body = "" if checked.get("body") is None else checked["body"]
                if (
                    checked.get("title") != title
                    or checked_body != body
                    or checked.get("draft") is not draft
                    or checked.get("state") != "open"
                    or checked.get("merged") is not False
                ):
                    raise DeliveryError("PR metadata or status changed during verification.")
            except DeliveryError as error:
                if updated:
                    raise DeliveryError(
                        f"PR metadata update may have occurred; verification failed: {error}",
                    ) from error
                raise
            return {
                "number": checked["number"],
                "url": checked["html_url"],
                "head": request["head"],
                "draft": draft,
                "updated": updated,
            }
        if action == "merge-pr":
            repository = self.repository(request)
            method = request.get("method", "merge")
            if not isinstance(method, str) or method not in {"merge", "squash", "rebase"}:
                raise DeliveryError("Unsupported PR merge method.")
            if not self.checks(request)["green"]:
                raise DeliveryError("Current PR checks are not green.")
            if self.pr(request).get("draft"):
                self.command(["gh", "pr", "ready", str(request["pr"]), "--repo", repository])
            if not self.checks(request)["green"]:
                raise DeliveryError("Checks changed after draft transition; merge stopped.")
            value = self.api_write(
                f"repos/{repository}/pulls/{request['pr']}/merge",
                "PUT",
                {
                    "sha": request["head"],
                    "merge_method": method,
                },
            )
            verified = self.pr(request)
            if (
                value.get("merged") is not True
                or verified.get("merged") is not True
                or verified.get("merge_commit_sha") != value.get("sha")
            ):
                raise DeliveryError(
                    "Merge response requires remote-state reconciliation; do not retry blindly.",
                )
            return {"merged": True, "merge_sha": value["sha"], "url": verified["html_url"]}
        if action == "sync-main":
            value = self.pr(request)
            merge_sha = sha(text_field(request, "merge_sha"))
            if value.get("merged") is not True or value.get("merge_commit_sha") != merge_sha:
                raise DeliveryError("Only an already verified remote PR merge may be synchronized.")
            if self.git("status", "--porcelain").strip():
                raise DeliveryError(
                    "Preserve owner changes; synchronization requires a clean checkout.",
                )
            self.git("fetch", "origin", "main")
            self.git("merge-base", "--is-ancestor", merge_sha, "origin/main")
            self.git("merge-base", "--is-ancestor", "main", "origin/main")
            self.git("switch", "main")
            self.git("pull", "--ff-only", "origin", "main")
            head = self.git("rev-parse", "HEAD").strip()
            if (
                head != self.git("rev-parse", "origin/main").strip()
                or self.git("status", "--porcelain").strip()
            ):
                raise DeliveryError(
                    "Synchronization completed but final clean-state verification failed.",
                )
            return {"branch": "main", "head": head}
        raise DeliveryError("Unsupported delivery action.")


def main() -> int:
    """Run this module's application or command-line entry point.

    Returns:
        Process exit status; zero indicates successful completion.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "inspect",
            "validate-message",
            "stage",
            "commit",
            "push",
            "draft-pr",
            "update-pr",
            "pr-info",
            "pr-checks",
            "merge-pr",
            "sync-main",
        ],
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--request")
    parser.add_argument("--authorized", action="store_true")
    args = parser.parse_args()
    try:
        if sys.platform != "win32":
            raise DeliveryError("Use the native Windows Python/Git/gh toolchain.")
        delivery = Delivery(args.root)
        request = (
            {}
            if args.request is None
            else mapping(
                json.loads(delivery.temporary_file(args.request).read_text(encoding="utf-8")),
            )
        )
        result = delivery.perform(args.action, request, args.authorized)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (DeliveryError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Delivery stopped: {error}. Inspect actual state before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
