# Dependency audit — 2026-10-13

This is a dated release-verification snapshot, not a claim that versions remain
latest indefinitely. During the M1 updates, Context7 supplied configuration
reference material; official PyPI, npm and GitHub release data supplied release
versions. Stable, non-yanked releases were selected, with prereleases disallowed
in `tool.uv`. `uv lock --upgrade` refreshed the Python resolution.

## Python

`uv.lock` contains 32 packages including the local project; the 31 external
packages below include the later Pydantic additions. Hatchling is pinned separately
in `[build-system]` because isolated build dependencies are not part of `uv.lock`.
Optional analysis/render packages are installed for compatibility validation;
their functionality is not implemented in M1.

| Python package                                                              | Pinned version |
| --------------------------------------------------------------------------- | -------------- |
| [annotated-types](https://pypi.org/project/annotated-types/0.8.0/)          | 0.8.0          |
| [ast-serialize](https://pypi.org/project/ast-serialize/0.13.0/)             | 0.13.0         |
| [colorama](https://pypi.org/project/colorama/0.4.6/)                        | 0.4.6          |
| [hatchling](https://pypi.org/project/hatchling/1.32.4/)                     | 1.32.4         |
| [iniconfig](https://pypi.org/project/iniconfig/2.3.1/)                      | 2.3.1          |
| [librt](https://pypi.org/project/librt/0.16.0/)                             | 0.16.0         |
| [mypy](https://pypi.org/project/mypy/2.4.0/)                                | 2.4.0          |
| [mypy-extensions](https://pypi.org/project/mypy-extensions/1.1.0/)          | 1.1.0          |
| [numpy](https://pypi.org/project/numpy/2.5.4/)                              | 2.5.4          |
| [packaging](https://pypi.org/project/packaging/26.3/)                       | 26.3           |
| [pandas](https://pypi.org/project/pandas/3.0.6/)                            | 3.0.6          |
| [pathspec](https://pypi.org/project/pathspec/1.1.1/)                        | 1.1.1          |
| [pillow](https://pypi.org/project/pillow/12.3.0/)                           | 12.3.0         |
| [pluggy](https://pypi.org/project/pluggy/1.6.0/)                            | 1.6.0          |
| [pydantic](https://pypi.org/project/pydantic/2.14.1/)                       | 2.14.1         |
| [pydantic-core](https://pypi.org/project/pydantic-core/2.50.1/)             | 2.50.1         |
| [pygments](https://pypi.org/project/pygments/2.21.0/)                       | 2.21.0         |
| [pyqtgraph](https://pypi.org/project/pyqtgraph/0.14.0/)                     | 0.14.0         |
| [pyside6](https://pypi.org/project/pyside6/6.12.0/)                         | 6.12.0         |
| [pyside6-addons](https://pypi.org/project/pyside6-addons/6.12.0/)           | 6.12.0         |
| [pyside6-essentials](https://pypi.org/project/pyside6-essentials/6.12.0/)   | 6.12.0         |
| [pyside6-pdf](https://pypi.org/project/pyside6-pdf/6.12.0.140/)             | 6.12.0.140     |
| [pyside6-webengine](https://pypi.org/project/pyside6-webengine/6.12.0.140/) | 6.12.0.140     |
| [pytest](https://pypi.org/project/pytest/9.1.1/)                            | 9.1.1          |
| [pytest-qt](https://pypi.org/project/pytest-qt/4.5.0/)                      | 4.5.0          |
| [python-dateutil](https://pypi.org/project/python-dateutil/2.9.0.post0/)    | 2.9.0.post0    |
| [ruff](https://pypi.org/project/ruff/0.17.0/)                               | 0.17.0         |
| [shiboken6](https://pypi.org/project/shiboken6/6.12.0/)                     | 6.12.0         |
| [six](https://pypi.org/project/six/1.17.0/)                                 | 1.17.0         |
| [typing-extensions](https://pypi.org/project/typing-extensions/4.16.0/)     | 4.16.0         |
| [typing-inspection](https://pypi.org/project/typing-inspection/0.4.4/)      | 0.4.4          |
| [tzdata](https://pypi.org/project/tzdata/2026.5/)                           | 2026.5         |

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
