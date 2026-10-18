# Developer-tool verification

The [delivery skill](../../.agents/skills/github-delivery/SKILL.md) owns helper
commands and separate tests. Application discovery excludes those tests.
[CI routing](../development/CI.md) and [quality policy](../development/CODE_QUALITY.md)
define when affected tooling checks are required.

Recorded native Windows evidence uses Python 3.14.6 / Node 26.11.1.
`uv run --locked pytest .agents/skills/github-delivery/tests` passed 81 cases
in the SciPy dependency-compatibility scope; skill Ruff/mypy checks passed.
`node --test tests/ci/changes.test.mjs` and actionlint passed their tested scopes.

Coverage includes isolated Git repositories, exact staging/message/destination
guards, PR metadata handling, cumulative routing and the PowerShell merge gate.
These results do not certify later helper changes, live GitHub mutations,
current branch protection or hosted label assignment. Tool tests are rerun only
when their implementation, tests or relevant dependencies change.
