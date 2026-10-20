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
    match = re.fullmatch(r"(0|[1-9]\d*)\.\d+\.\d+((?:a|b|rc)\d+)?", version)
    if match is None or tag != f"v{version}":
        raise ValueError("Tag must match a supported project.version")
    return match[1] == "0" or match[2] is not None


def verify_main_ancestry(root: Path, commit: str) -> None:
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
    verify_merged_prs(json.loads(response), args.repository)
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
    print("Release policy passed: version, tag SHA, main ancestry and merged PR")
