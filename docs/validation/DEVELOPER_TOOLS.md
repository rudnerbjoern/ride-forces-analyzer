# Developer-tool verification

Delivery helper tests are separate from application discovery. Current commands
and operation constraints belong to the [delivery skill](../../.agents/skills/github-delivery/SKILL.md),
[CI guide](../development/CI.md) and [quality guide](../development/CODE_QUALITY.md).

## Recorded native Windows evidence

Python 3.14.6 / Node 26.11.1; results are scoped to the tested tooling and do not
certify later changes or live GitHub mutations.

| Command / scope                                                                                                                                                                                                                                                               | Result                                                                   |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `uv run pytest .agents/skills/github-delivery/tests --collect-only -q` — separated discovery                                                                                                                                                                                  | 53 cases collected, excluded from ordinary application discovery         |
| `uv run pytest .agents/skills/github-delivery/tests/test_github_delivery.py::test_windows_cli_reports_review_state_without_mutating_index .agents/skills/github-delivery/tests/test_github_delivery.py::test_stage_commit_and_push_preserve_unrelated_work_and_exact_message` | 2 passed, 8.74 s                                                         |
| `uv run pytest .agents/skills/github-delivery/tests -k update_pr` and affected metadata regressions                                                                                                                                                                           | All 28 metadata cases plus draft/reuse checks passed across focused runs |
| `uv run --locked pytest .agents/skills/github-delivery/tests` — Stage 3 dependency compatibility                                                                                                                                                                              | 81 passed, 61.24 s; `.tmp/stage3-*` evidence                             |
| `node --test tests/ci/changes.test.mjs`                                                                                                                                                                                                                                       | 40 passed in Stage 3 verification                                        |
| `.tmp/m1-actionlint/actionlint.exe .github/workflows/ci.yml`                                                                                                                                                                                                                  | Accepted, actionlint 1.7.12                                              |

Skill Ruff lint/format and its strict mypy commands passed (3 files / 2 Python
files) in the dependency-compatibility run. Git transport/metadata mutations are
simulated or confined to isolated `.tmp/` repositories; no live metadata-write
claim follows. CI gate tests cover selection combinations, failed/cancelled/missing
jobs and actual PowerShell behavior. Hosted updater success and fresh-session
skill discovery require separate evidence. Application changes do not require
repeating this suite when its inputs/environment are unchanged.
