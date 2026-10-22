---
name: github-delivery
description: Deliver reviewed Ride Forces Analyzer changes through Git commits, pushes and draft PRs; update PR metadata, inspect PR checks, perform explicitly authorized merges and synchronize local main.
---

# GitHub delivery

Use for this repository's Git/GitHub delivery operations. Read
[AGENTS.md](../../../AGENTS.md) and the
[commit policy](../../../.github/commit-message-instructions.md).
Creating/using this skill grants no mutation permission.

## Permanent workflow

- Obtain explicit owner authorization for each requested mutation and exact scope.
  Commit/push/draft authorization never authorizes merge. PR checks are read-only.
- Use the [shared helper](scripts/git_delivery.py), optionally through the
  [Windows wrapper](scripts/git-delivery.ps1). Do not generate replacement operation
  scripts. Use Windows Git/gh and the configured uv/Python toolchain.
- Keep request JSON, exact scope arrays, commit messages and PR bodies in `.tmp/`.
  Never store tokens, current branch names, commit IDs or authorization in this skill.
- Complete local acceptance and final documentation before publication. Reuse valid
  unchanged evidence; never rerun suites solely because publication was authorized.
- Inspect status, branch, head, origin URL, staged paths and fingerprint once.
  Preserve owner changes. Stage only an explicitly approved scope into an empty
  index; an already reviewed index may be committed only if it matches that scope.
- Review only the staged diff before authoring a commit message. Refresh the
  staged fingerprint after review; supply it to commit. Stop on any mismatch.
- Supply the current verified head for push/PR/check/merge operations. Never
  force-push, bypass checks, amend/reset, delete branches or push to `main`.
- Create a draft targeting `main`; reuse an existing matching PR without creating
  a duplicate or changing its draft status. Stop on ambiguous API errors; inspect
  remote state before any retry. Report mutations that succeeded before a later failure.
- Update an existing PR's title/body with `update-pr` and explicit authorization.
  Use request JSON and a UTF-8 body file in `.tmp/`; never pass metadata through
  shell-quoted `gh pr edit` arguments or ad hoc operation scripts. The helper writes
  only title/body, verifies repository/base/head and preserves draft/open status.
- Merge only after explicit authorization, matching repository/base/head and green
  checks for that revision. Require the final `CI` / `check` job to succeed; other
  checks must pass or be legitimately skipped. A pending/failed/unknown result
  blocks merge. Recheck after marking a draft ready; use the expected-head merge guard.
- Verify the merge remotely. Synchronize local `main` only from the already merged
  remote branch, with a clean working tree and fast-forward ancestry. Never stash
  or overwrite owner changes. Do not delete the feature branch automatically.

## Commit messages and PR titles

The linked commit policy is authoritative. Read it before generating a message;
the helper derives its icon/type mapping from that file.

- Title: `:<icon>: <type>(<scope>): <imperative outcome>`, English.
  Commit titles: at most 80 raw characters. Lower-case type/scope and initial summary
  letter; no final period.
- Choose the type from the staged outcome and its matching icon. Scope names the
  affected capability; never infer content from unstaged files.
- Apply the same title rules to draft PR creation and PR title updates, except the
  80-character limit: it does not apply to PR titles. Describe
  the complete current PR diff against `main`, not just the latest commit or staged
  files. PR descriptions follow the repository PR template, not commit-body rules.
- Omit the body for a small self-explanatory change. Otherwise use `Why:` then
  `Changes:` with material effects. Preserve real newlines; use a message file.
- Reference only actual issues/milestones. Include `BREAKING CHANGE:` when needed.
  State only actual validation; distinguish local evidence from hosted CI.
- Never include credentials, GPS positions, recording payloads or invented results.
  English, imperative wording, relevance, reference validity and truth require agent
  review; mechanical validation alone cannot prove them. GitHub-generated merge
  metadata is not a new staged-change message to invent.

## Helper invocation

From the repository root in Windows PowerShell:

```powershell
uv run --locked python .agents/skills/github-delivery/scripts/git_delivery.py inspect
uv run --locked python .agents/skills/github-delivery/scripts/git_delivery.py commit --request .tmp/delivery.json --authorized
uv run --locked python .agents/skills/github-delivery/scripts/git_delivery.py update-pr --request .tmp/pr-update.json --authorized
```

Every mutation requires `--authorized`, supplied only after the owner's actual
permission. This flag is an accident guard, not an independent proof of permission.
All actions accept `--root` for an explicitly selected checkout and return JSON.
Use a JSON object in `--request`; paths below must resolve inside that checkout's `.tmp/`.

| Action             | Request fields                                                             |
| ------------------ | -------------------------------------------------------------------------- |
| `inspect`          | None; returns head, branch, origin URL, staged paths and fingerprint.      |
| `stage`            | `branch`, `head`, `scope_file` (JSON array of exact relative paths).       |
| `validate-message` | `message_file`; checks title/body mechanics without mutation.              |
| `commit`           | `branch`, `head`, `scope_file`, `fingerprint`, `message_file`.             |
| `push`             | `branch`, `head`, `remote_url`; uses only origin and an explicit ref.      |
| `draft-pr`         | Push fields plus `repository`, `title`, `body_file`.                       |
| `pr-info`          | `repository`, `remote_url`, `pr`; returns title/body and state.            |
| `pr-checks`        | PR-info fields plus `branch`, `head`; reports green/pending/blocked.       |
| `update-pr`        | PR-check fields plus `title`, `body_file`; requires authorization.         |
| `merge-pr`         | PR-check fields; optional `method`: `merge` (default), `squash`, `rebase`. |
| `sync-main`        | PR-check fields plus verified `merge_sha`; owner-authorized sync.          |

After commit, use the returned new head for subsequent requests. On cancellation,
transport errors, changed refs or partial failures, stop and report actual state;
never retry a mutation blindly. `update-pr` skips identical metadata. Its
[REST endpoint](https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request)
has no atomic head-SHA condition: pre/post reads detect changes but cannot prevent
races during PATCH. A failed verification may follow a successful write; inspect
remote state without automatically retrying or restoring old metadata.
Live remote mutation is not part of skill tests.

## Skill regression checks

Keep these developer-tool tests outside application pytest/Test Explorer discovery.
Run them only after changes to this skill's executable code/tests, the commit policy
or relevant Python/Git environment inputs. Ordinary application changes and delivery
operations do not require rerunning this suite; reuse valid unchanged evidence.

```powershell
uv run ruff check .agents/skills/github-delivery
uv run ruff format --check .agents/skills/github-delivery
uv run mypy .agents/skills/github-delivery/scripts/git_delivery.py .agents/skills/github-delivery/tests/test_github_delivery.py
uv run pytest .agents/skills/github-delivery/tests
```

Tests use isolated repositories under `.tmp/` and simulated GitHub transport.
The conditional `skills` CI job runs these checks for affected PRs only; see
[CI selection](../../../docs/development/CI.md).
