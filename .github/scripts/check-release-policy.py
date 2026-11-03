"""Qualify an existing version tag for automatic source publication.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib


def is_prerelease(tag: str, version: str) -> bool:
    """Classify a matching supported version tag under the release policy.

    Args:
        tag: Version tag selected for lookup, validation or suppression.
        version: Version string to format or validate.

    Returns:
        True when the requested check succeeds or the event is handled; otherwise False.

    Raises:
        ValueError: Tag must match a supported project.version.
    """
    match = re.fullmatch(r"(0|[1-9]\d*)\.\d+\.\d+((?:a|b|rc)\d+)?", version)
    if match is None or tag != f"v{version}":
        raise ValueError("Tag must match a supported project.version")
    return match[1] == "0" or match[2] is not None


def verify_main_ancestry(root: Path, commit: str) -> None:
    """Require a full commit identity contained in remote main.

    Args:
        root: Checkout or data root used to resolve the operation's paths.
        commit: Full commit SHA selected for ancestry or release validation.

    Returns:
        None.

    Raises:
        ValueError: Expected a full commit SHA.
        subprocess.CalledProcessError: If the checked subprocess exits unsuccessfully.
    """
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Expected a full commit SHA")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"],
        cwd=root,
        check=True,
        capture_output=True,
        timeout=30,
    )


def verify_merged_prs(value: object, repository: str) -> None:
    """Require an associated merged pull request targeting the selected main branch.

    Args:
        value: Candidate value to validate, format or store.
        repository: GitHub owner/repository identity expected to match origin.

    Returns:
        None.

    Raises:
        ValueError: Invalid associated PR response. Release commit requires an associated
            merged PR targeting main.
    """
    if not isinstance(value, list):
        raise ValueError("Invalid associated PR response")
    for pr in value:
        if not isinstance(pr, dict) or not pr.get("merged_at"):
            continue
        base = pr.get("base")
        if not isinstance(base, dict) or base.get("ref") != "main":
            continue
        repo = base.get("repo")
        if isinstance(repo, dict) and repo.get("full_name") == repository:
            return
    raise ValueError("Release commit requires an associated merged PR targeting main")


def reusable_application_checks(root: Path, commit: str, repository: str, prs: object) -> bool:
    """Reuse green PR application/UI jobs only for identical content and runner images.

    Args:
        root: Checkout containing the release and merged PR commits.
        commit: Validated release commit SHA.
        repository: GitHub owner/repository identity.
        prs: Associated pull requests returned by the release-policy lookup.

    Returns:
        Whether both expensive application jobs have reusable hosted evidence.
        Missing, changed or unavailable evidence requires fresh checks.
    """
    image = os.environ.get("ImageVersion")
    if not image or os.environ.get("GITHUB_WORKFLOW_SHA") != commit or not isinstance(prs, list):
        return False
    try:
        pr = next(pr for pr in prs if isinstance(pr, dict) and pr.get("merged_at"))
        verify_merged_prs([pr], repository)
        head = pr["head"]["sha"]
        if not isinstance(head, str) or not re.fullmatch(r"[a-f0-9]{40}", head):
            return False
        trees = subprocess.check_output(
            ["git", "rev-parse", f"{commit}^{{tree}}", f"{head}^{{tree}}"],
            cwd=root,
            text=True,
            timeout=30,
        ).splitlines()
        if len(trees) != 2 or trees[0] != trees[1]:
            return False
        prefix = f"repos/{repository}/actions"
        runs = json.loads(
            subprocess.check_output(
                [
                    "gh",
                    "api",
                    f"{prefix}/workflows/ci.yml/runs?event=pull_request&head_sha={head}&per_page=1",
                ],
                text=True,
                encoding="utf-8",
                timeout=60,
            ),
        )["workflow_runs"]
        if not runs:
            return False
        run = runs[0]
        if (
            run["head_sha"] != head
            or run["event"] != "pull_request"
            or run["path"] != ".github/workflows/ci.yml"
            or run["head_repository"]["full_name"] != repository
            or run["status"] != "completed"
            or run["conclusion"] != "success"
        ):
            return False
        jobs = json.loads(
            subprocess.check_output(
                ["gh", "api", f"{prefix}/runs/{run['id']}/jobs?filter=latest&per_page=100"],
                text=True,
                encoding="utf-8",
                timeout=60,
            ),
        )["jobs"]
        for name in ("check", "Application quality and tests", "User interface and screenshots"):
            matches = [job for job in jobs if job["name"] == name]
            if (
                len(matches) != 1
                or matches[0]["status"] != "completed"
                or matches[0]["conclusion"] != "success"
            ):
                return False
            if name == "check":
                continue
            log = subprocess.check_output(
                ["gh", "api", f"{prefix}/jobs/{matches[0]['id']}/logs"],
                text=True,
                encoding="utf-8",
                timeout=60,
            )
            runner = re.search(r"\bImage: windows-\S+\r?\n[^\n]*\bVersion: ([0-9.]+)", log)
            tested = re.findall(r"Tested tree: ([a-f0-9]{40})", log)
            if runner is None or runner[1] != image or tested != [trees[0]]:
                return False
        print(f"Reuse application/UI checks from PR #{pr['number']}, CI run {run['id']} ({head})")
        return True
    except OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError:
        print("PR application/UI evidence unavailable; run full application checks")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    preview = is_prerelease(args.tag, version)
    verify_main_ancestry(root, args.sha)
    tagged = subprocess.check_output(
        ["git", "rev-parse", f"refs/tags/{args.tag}^{{commit}}"],
        text=True,
        timeout=30,
    ).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=30).strip()
    if tagged != args.sha or head != args.sha:
        raise ValueError("Tag, checkout and event SHA must identify the same commit")
    response = subprocess.check_output(
        ["gh", "api", f"repos/{args.repository}/commits/{args.sha}/pulls?per_page=100"],
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    prs = json.loads(response)
    verify_merged_prs(prs, args.repository)
    reuse = reusable_application_checks(root, args.sha, args.repository, prs)
    if not reuse:
        print("Run fresh application/UI checks: no complete matching PR evidence")
    directory = root / ".tmp/release"
    directory.mkdir(parents=True, exist_ok=True)
    notes = (root / "docs/development/RELEASE_NOTES.md").read_text(encoding="utf-8")
    notes = (
        notes.replace("{{VERSION}}", version)
        .replace(
            "{{REPOSITORY}}",
            args.repository,
        )
        .replace("{{TAG}}", args.tag)
    )
    (directory / "release-notes.md").write_text(notes, encoding="utf-8")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"prerelease={str(preview).lower()}\n")
        output.write(f"version={version}\n")
        output.write(f"reuse-application-checks={str(reuse).lower()}\n")
    print("Release policy passed: version, tag SHA, main ancestry and merged PR")
