# Codex project settings

`.codex/config.toml` contains project defaults. Workflow and safety instructions
remain in [AGENTS.md](../../AGENTS.md). Keep personal credentials out of this file.
Project defaults do not modify the user-global configuration.

## Current settings

- Model: `gpt-6.1-sol`; reasoning effort: `high`; personality: `pragmatic`.
- Web search: `cached`.
- Context7 MCP server: `npx -y @upstash/context7-mcp`.
- Memory feature enabled; `generate_memories` and `use_memories` enabled.
- `disable_on_external_context = true` excludes threads containing external context,
  such as MCP or web-search results, from memory generation.

Context7 requires Node.js/npm in the environment hosting Codex and network access
for documentation lookup. It is a development aid, not an application runtime
requirement. The server package is not pinned in this requested configuration;
it is separate from the locked Python and Node project dependencies.

Codex reads project configuration only for trusted repositories. User/profile and
CLI settings also participate in configuration precedence; project defaults do
not guarantee the active model or tool availability in every session. See the
[official configuration guide](https://learn.chatgpt.com/docs/config-file/config-basic).

The requested memory keys are documented in the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
They configure Codex behavior; they do not authorize editing memory files manually.

## GitHub delivery skill

The repository-local [github-delivery skill](../../.agents/skills/github-delivery/SKILL.md)
defines the authorized delivery workflow and supplies a shared Windows Git/gh
helper for exact staging, commit validation, push, draft PRs, checks, merge and
safe synchronization. Commit titles/text follow the authoritative
[commit policy](../../.github/commit-message-instructions.md); mechanical checks
do not prove English wording, semantic scope, valid references or evidence truth.
Runtime requests and message/body files stay under `.tmp/`. The helper's authorization
flag prevents accidental calls; actual owner approval remains mandatory.
Skill Markdown participates in documentation checks. Scripts and regression tests
have their own conditional `skills` CI job; ordinary application checks exclude them.
The tests live under `.agents/skills/github-delivery/tests/`, outside the default
pytest `tests/` path and VS Code application discovery. Run
`uv run pytest .agents/skills/github-delivery/tests` only when the skill implementation,
tests, commit policy or relevant environment inputs change. See the skill for its
separate lint/format/type commands and [CI selection](CI.md) for routing.

Before suite separation, native Windows verification on 2026-10-13: focused helper validation passed
50 cases, then the complete `uv run pytest` suite passed 888 cases, including
52 skill cases and both GUI tests. The final immutable-SHA push refinement was
subsequently verified with seven affected push regression cases; unrelated passing
evidence was reused. Ruff lint/format passed (39 Python files), mypy passed
23 files, Pyright reported zero errors/warnings, and the 11 type contracts,
12 dependency cases and 35 CI cases passed. Lock validation resolved 32 packages.
The extended documentation suite passed 34 link cases, Markdownlint checked
34 files and CSpell checked 90 files without issues. Skill Creator's
`quick_validate.py` accepted the skill metadata.

The Windows wrapper's `inspect` action was tested in the real checkout; the
helper's read-only `pr-checks` verified PR #8 at published revision `36b203f`.
That hosted result does not validate these uncommitted skill changes. GitHub
mutations were simulated; Git writes/pushes occurred only in isolated `.tmp/`
repositories. Fresh-session automatic skill discovery remains unverified.

After suite separation on the same date, `uv run pytest` passed all 836 application
tests (including both native GUI tests) in 80.17 seconds. The explicit command
`uv run pytest .agents/skills/github-delivery/tests --collect-only -q` found all
53 skill cases in 0.13 seconds; none appeared in application discovery. The two
relocation smoke tests were run explicitly:

```powershell
uv run pytest .agents/skills/github-delivery/tests/test_github_delivery.py::test_windows_cli_reports_review_state_without_mutating_index .agents/skills/github-delivery/tests/test_github_delivery.py::test_stage_commit_and_push_preserve_unrelated_work_and_exact_message
```

Both passed in 8.74 seconds. The move changes only the tests' repository-root
lookup; helper behavior is unchanged. The full slow skill suite was not repeated.
Separate skill Ruff lint/format passed (three files), and the documented skill mypy
command passed both Python files. CI selection passed 39 tests, including 31 real
PowerShell gate scenarios; actionlint 1.7.12 accepted the updated workflow.
`npm run typecheck` reported zero errors/warnings after application discovery changed.
Regular `uv run ruff check .` and `uv run ruff format --check src tests` passed
(37 formatted files). `npm run test:docs` passed 34 link cases; Markdownlint checked
34 files and CSpell checked 90 files with zero issues. The new hosted `skills` job
has not run on GitHub yet; only local routing, gate and workflow syntax are verified.

## Configuration validation boundary

The file was parsed as TOML, and the local Codex CLI accepted it when listing
features with `memories` enabled. A new Codex session using all requested settings,
Context7 startup from this file and actual memory generation were not exercised.
No such runtime verification is claimed.
