# Source release validation

Scope: proposed `v0.1.0` source preview, based on
`fe467461e00494c00297d3938b2c1e95e49adf24` plus the licensed-source,
documentation and editor-configuration changes delivered with this report.
Native Windows x64 desktop; Python 3.14.6, uv 0.13.0, Node 26.11.1.
This qualifies the tested source candidate, not a published tag or an installer.

| Command                                         | Result                                                     |
| :---------------------------------------------- | :--------------------------------------------------------- |
| `uv lock --check`                               | Passed                                                     |
| `uv run --locked ruff check .`                  | Passed                                                     |
| `uv run --locked ruff format --check src tests` | 92 files formatted                                         |
| `uv run --locked mypy src`                      | 58 source files; no issues                                 |
| `npm run typecheck`                             | No errors or warnings                                      |
| `npm run test:types`                            | 11 passed                                                  |
| `npm run test:dependencies`                     | 15 passed                                                  |
| `node --test tests/ci/changes.test.mjs`         | 41 passed                                                  |
| `uv run --locked pytest`                        | 1,442 passed; no skips                                     |
| `npm run test:docs`                             | Markdown/spelling passed; 49 link tests before this report |

An index-derived ZIP candidate contains 198 files, five byte-identical original
recordings and both CC BY-SA notices plus GPL/third-party notices. Python AST
comparison excludes module documentation strings and confirms unchanged executable logic.
Gitleaks `dir` with the default rules, inline allow comments disabled and redacted
output reports no findings for this source snapshot. Previous full-history review
does not extend to hosted assets or newly published content automatically.

Fresh ZIP extraction and `setup.ps1` succeeded with an independent `.venv`.
The extracted environment passed 16 focused pytest cases: actual module startup,
light/dark and language behavior, original GPS preservation, both-aspect production
previews, and CPU ProRes/H.264 encoding with decoding checks. The pinned uv and
FFmpeg tools were supplied locally under `.tmp/`; no tools were included in the
ZIP. This is a fresh environment on the existing workstation, not a clean VM or
a fresh network-download test. Installed application and local checks work offline.

Temporary commands and runner output: `.tmp/release-checks.py`,
`.tmp/release-check-*.log`, `.tmp/prepare-release-source.py`,
`.tmp/release-source-setup.py`, `.tmp/release-source-smoke.py` and associated logs.
Final documentation checks cover this report separately. GitHub checks, review,
merge, final tag/archive identity and public release remain separate gates.
