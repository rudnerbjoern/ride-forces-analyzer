# Python validation and code quality

Install tools and run the canonical checks in [Windows setup](SETUP.md).
All installed checks work offline. Configuration lives in `pyproject.toml` and
`.vscode/settings.json`; [AGENTS.md](../../AGENTS.md) governs evidence reuse.

## Runtime and static contracts

`config.AppSettings` is an immutable, strict Pydantic bootstrap model. It rejects
unknown keys, empty titles, coercion from strings/floats/booleans and dimensions
outside 1–16,777,215 (Qt's widget limit). Defaults are validated. Recording/source
models use owned frozen dataclasses; their [contracts](CANONICAL_MODELS.md) and
[analysis contracts](ANALYSIS_MODELS.md) are separate from window settings.

- Ruff uses Python 3.14, 100 columns, `F`/`COM812`, LF and magic trailing commas.
  Format checks report drift without rewriting files; COM812 is intentional.
- mypy checks `src/` strictly with Pydantic's typed-constructor plugin.
- Pylance/Pyright share strict Windows Python 3.14 configuration for `src/` and
  `tests/`, excluding dependencies/caches. CLI Pyright is lock-pinned; its engine
  version may differ from the editor's. CLI success does not verify editor UI.
- VS Code uses the selected Windows interpreter and locked Ruff executable,
  formats on save and applies explicit-save fixes. See setup for interpreter selection.

## Test coverage

| Test group                                                                    | Contract                                                                                                         |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `test_project.py`, `test_fixture_inventory.py`                                | Exact five-file inventory, byte lengths/SHA-256, recursive schema observations                                   |
| `test_settings.py`, `test_gui.py`                                             | Strict settings/bounds, native module startup, exposed window, resize and close                                  |
| `test_ruff.py`                                                                | F401/COM812, accepted LF formatting and rejected drift/CRLF                                                      |
| `test_source_models.py`, `test_recording_models.py`, `test_import_results.py` | Ownership, immutability, absence/defaults, source types and ordered outcomes                                     |
| `test_decoder.py`, `test_motion_parser.py`, `test_optional_parser.py`         | Strict grammar/budgets, complete vectors/indices, optional metadata/attributes/GPS                               |
| `test_import_service.py`                                                      | Full Path/bytes ingestion, repeated/concurrent results, shared budgets and fresh-process network/write/Qt guards |
| `test_analysis_models.py`, `test_device_analysis.py`                          | Owned NumPy data, capability/unit/provenance gates, synthetic device norms and Pint conversion                   |
| `tests/types/*.test.mjs`                                                      | Pyright constructor/frozen-field/mapping contracts and result-union narrowing                                    |
| `tests/dependencies/*.test.mjs`                                               | Actual Node consumer regressions, Dependabot and label policy                                                    |
| `tests/ci/changes.test.mjs`                                                   | Full-PR routing and the real PowerShell merge gate                                                               |

Type-contract tests require analyzed files and expected diagnostic rules, not just
an exit code. `tests/benchmark_importer.py` measures timing/Python allocations
without performance assertions. Source-data tests retain original bytes and
scientific unknowns; numerical synthetic success does not qualify real sensors.
The [dependency policy](DEPENDABOT.md#node-overrides-and-security-boundary) records
override rationale and security limits. These Node tests are development tooling, not rendering.

Developer-tool regressions under `.agents/skills/` remain outside application
discovery; their [skill instructions](../../.agents/skills/github-delivery/SKILL.md)
define when to run them. [CI selection](CI.md) describes the corresponding jobs.

## Test design

Test each responsibility at its own boundary. Keep exhaustive cheap cases for
parser errors, numerical edges, source preservation and translation placeholders.
Check layout geometry, glyph bounds and alpha directly in rendered frames for
every supported layout/aspect. Test video-rate mapping independently of repeated
full-frame rendering.

Real encoder integration uses eight representative cases covering output codec ×
aspect × CPU/GPU preference, with every layout represented and German examples
included. GPU preference may fall back to CPU; command-contract tests verify GPU
options independently of installed hardware. Batch integration uses two real jobs
with different rides/formats; pure queue tests own the full ride/preset cross-product.
Run shared GUI progress/cancellation once; test layout-specific controls in the
existing interaction checks. Add variants only for distinct risks, not to multiply
every independent option across an expensive end-to-end workflow.

GUI layout references use a 3840 × 2160 editing desktop at 150% and 200%
scaling: logical working areas of 2560 × 1400 and 1920 × 1040 reserve taskbar
space. Shared interaction fixtures use the latter; export layout checks use both
with English/German text. These are test-controlled Qt client sizes, independent
of the runner's physical monitor. Native startup separately checks actual desktop
constraints. Compact layouts retain targeted navigation/scrolling regressions,
not a second full workflow matrix. Video frame resolution and portrait/landscape
export tests remain independent of desktop size. A layout check on a smaller CI
desktop does not establish visual acceptance on a physical 4K display.

## Primary references

- [Pydantic configuration](https://docs.pydantic.dev/latest/concepts/config/) and
  [mypy integration](https://docs.pydantic.dev/latest/integrations/mypy/).
- [Ruff editor settings](https://docs.astral.sh/ruff/editors/settings/).
- [Pylance/Pyright configuration](https://github.com/microsoft/pylance-release/blob/main/USING_WITH_PYRIGHT.md).
- [Qt widget size](https://doc.qt.io/qt-6/qwidget.html#QWIDGETSIZE_MAX).
