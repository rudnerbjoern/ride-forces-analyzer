# Locked dependency inventory

Current versions come from repository manifests/locks, not a claim that packages
are latest or free of vulnerabilities. `uv.lock` contains 37 packages including
the local project. Optional installed packages do not imply implemented features;
see [roadmap](../ROADMAP.md). License/compatibility boundaries are in ADR 0004 via
the [architecture decision index](../architecture/09_architecture_decisions.md).

## Python

| Package            | Locked version |
| ------------------ | -------------- |
| annotated-types    | 0.8.0          |
| ast-serialize      | 0.13.0         |
| colorama           | 0.4.6          |
| flexcache          | 0.3            |
| flexparser         | 0.4            |
| iniconfig          | 2.3.1          |
| librt              | 0.16.0         |
| mypy               | 2.4.0          |
| mypy-extensions    | 1.1.0          |
| numpy              | 2.5.4          |
| packaging          | 26.3           |
| pandas             | 3.0.6          |
| pathspec           | 1.1.1          |
| pillow             | 12.3.0         |
| pint               | 0.26.1         |
| platformdirs       | 4.13.0         |
| pluggy             | 1.6.0          |
| pydantic           | 2.14.1         |
| pydantic-core      | 2.50.1         |
| pygments           | 2.21.0         |
| pyqtgraph          | 0.14.0         |
| pyside6            | 6.12.0         |
| pyside6-addons     | 6.12.0         |
| pyside6-essentials | 6.12.0         |
| pyside6-pdf        | 6.12.0.140     |
| pyside6-webengine  | 6.12.0.140     |
| pytest             | 9.1.1          |
| pytest-qt          | 4.5.0          |
| python-dateutil    | 2.9.0.post0    |
| ruff               | 0.17.0         |
| scipy              | 1.18.1         |
| shiboken6          | 6.12.0         |
| six                | 1.17.0         |
| typing-extensions  | 4.16.0         |
| typing-inspection  | 0.4.4          |
| tzdata             | 2026.5         |

Hatchling is pinned separately in `pyproject.toml` build-system metadata because
isolated build dependencies are not part of `uv.lock`. Setup uses the complete
locked environment; see [Windows setup](../development/SETUP.md).

## Node development tools

The verified Node.js runtime is 26.11.1 with bundled npm 11.20.0. Node.js is
not a desktop runtime requirement. `package-lock.json` pins the transitive tree
and integrity hashes for these direct development tools:

- markdownlint-cli2 0.23.3, providing markdownlint 0.41.1.
- markdown-it 15.0.2 for local Markdown-link parsing.
- Pyright 1.1.414 for CLI typing and static Pydantic contracts.
- CSpell 10.3.6 with bundled offline dictionaries.

Release data came from the [official Node.js releases](https://nodejs.org/en/download/releases)
and the npm registry entries for [markdownlint-cli2](https://www.npmjs.com/package/markdownlint-cli2),
[markdown-it](https://www.npmjs.com/package/markdown-it),
[Pyright](https://www.npmjs.com/package/pyright) and [CSpell](https://www.npmjs.com/package/cspell).

## Workflow actions and environment

- [Checkout 7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1).
- [setup-uv 10.3.0](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.0).
- [uv 0.13.0](https://github.com/astral-sh/uv/releases/tag/0.13.0).
- [setup-node 7.1.0](https://github.com/actions/setup-node/releases/tag/v7.1.0).
- [actionlint 1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12)
  was used for static workflow validation from ignored `.tmp/`; it is not a project dependency.

Context7 references: [uv lock and sync](https://docs.astral.sh/uv/concepts/projects/sync/),
[setup-uv inputs](https://github.com/astral-sh/setup-uv/blob/main/README.md) and
[GitHub pull-request events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).

The requested Context7 launcher in `.codex/config.toml` is unpinned and is
separate from these locked project dependencies; see [Codex settings](../development/CODEX.md).
Actual validation results and acceptance evidence are recorded in [M1 validation](M1.md).

[Security evidence](DEPENDABOT.md) records the checked Node overrides and advisory
limits. No fresh online release/security audit is implied by this lock inventory.
