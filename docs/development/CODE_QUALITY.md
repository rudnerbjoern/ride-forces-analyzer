# Code quality and validation

Install tools and run the canonical checks in [Windows setup](SETUP.md).
All installed checks work offline. Configuration lives in `pyproject.toml` and
`.vscode/settings.json`; [AGENTS.md](../../AGENTS.md) governs evidence reuse.

## Runtime and static contracts

`config.AppSettings` is an immutable, strict Pydantic bootstrap model. It rejects
unknown keys, empty titles, coercion from strings/floats/booleans and dimensions
outside 1–16,777,215 (Qt's widget limit). Defaults are validated. Recording/source
models use owned frozen dataclasses; their [contracts](CANONICAL_MODELS.md) and
[analysis contracts](ANALYSIS_MODELS.md) are separate from window settings.

Preference setters validate inputs at runtime without coercion: language and
appearance accept only their declared choices, update consent requires a boolean,
timestamps must be finite numbers, tags require strings and directory tracking
requires `Path` objects. Export frame rates retain supported-rate validation.
Invalid inputs raise `ValueError` before changing storage. Keys are statically
restricted to supported names. SQLite stores text values; invalid stored values
and unavailable storage retain safe defaults.

- Ruff uses Python 3.14, 100 columns, `F`/`COM812`, LF and magic trailing commas.
  Format checks report drift without rewriting files; COM812 is intentional.
- mypy checks `src/` strictly with Pydantic's typed-constructor plugin.
- Pylance/Pyright share strict Windows Python 3.14 configuration for `src/` and
  `tests/`, excluding dependencies/caches. CLI Pyright is lock-pinned; its engine
  version may differ from the editor's. CLI success does not verify editor UI.
- VS Code uses the selected Windows interpreter and locked Ruff executable,
  formats on save and applies explicit-save fixes. See setup for interpreter selection.

## Test coverage

Python suites live under `tests/<subsystem>/test_<behavior>.py`:

| Directory                        | Responsibility                                                         |
| :------------------------------- | :--------------------------------------------------------------------- |
| domain                           | Source ownership and immutable recording models                        |
| importers                        | Decoding, motion, optional fields, diagnostics and Path/bytes import   |
| analysis                         | Analysis models, device/frame math, source references and extrema      |
| explorer                         | Qt-independent presentation, selections and GPS geometry               |
| rendering                        | Frames, layouts, previews, encoding, progress, estimates and batches   |
| storage                          | Persistent application preferences                                     |
| localization                     | Translation catalog, overlay text and OS language defaults             |
| ui                               | Native Qt startup, explorer, dialogs, appearance and user interactions |
| updates                          | Release discovery, transport and update preferences                    |
| recordings                       | Original fixture hashes and recursive schema inventory                 |
| packaging                        | Release policy, source archives and Windows packages                   |
| tooling                          | Application settings/version and Ruff contracts                        |
| support                          | Shared fixture paths, pinned identities and inventory helper           |
| types / dependencies / ci / docs | Separate Node type, dependency, CI and documentation checks            |

Type-contract tests require analyzed files and expected diagnostic rules, not just
an exit code. `tests/importers/benchmark.py` measures timing/Python allocations
without performance assertions. Source-data tests retain original bytes and
scientific unknowns; numerical synthetic success does not qualify real sensors.
The [dependency policy](DEPENDENCIES.md#node-overrides-and-security-boundary) records
override rationale and security limits. These Node tests are development tooling, not rendering.

Run a subsystem directly, for example `uv run --locked pytest tests/importers`
or `uv run --locked pytest tests/ui/test_export.py`. Names describe behavior;
folders identify the responsible subsystem. No additional marker matrix is needed.
Shared data fixtures live in `tests/conftest.py`; GUI-only fixtures and preference
isolation live in `tests/ui/conftest.py`. Reusable waits and workspace sizing
are in `tests/ui/helpers.py`; original recording constants are in
`tests/support/recordings.py`. Original `.forces` files remain under `tests/fixtures/`.

Developer-tool regressions under `.agents/skills/` remain outside application
discovery; their [skill instructions](../../.agents/skills/github-delivery/SKILL.md)
define when to run them. [CI selection](CI.md) describes the corresponding jobs.

## Recording model and service coverage

The locked development tools `coverage.py` and `pytest-cov` report coverage only for
`analysis.recording` and `analysis.service`, including branches, using
`[tool.coverage.*]` in `pyproject.toml`. Collection uses the analysis source
directory without importing modules to discover them. Run from the repository
root on native Windows:

```powershell
uv run --locked pytest --cov --cov-report=term-missing `
    tests/analysis/test_recording.py tests/analysis/test_recording_validation.py `
    tests/analysis/test_recording_preparation.py tests/analysis/test_recording_recalculation.py `
    tests/analysis/test_service.py `
    tests/analysis/test_taron_analysis_parity.py
uv run --locked coverage html
uv run --locked coverage json
```

The measurement replaces the previous data; it does not append old executions.
`pytest --cov` prints per-file results and fails if tests fail or coverage is below
the configured 100% threshold. At that threshold each reported module must be
fully covered. `coverage report` can also check an existing measurement.
All data, the HTML report (`html/index.html`) and
machine-readable JSON stay under `.tmp/coverage/analysis/`.

The gate is separate from ordinary pytest and is not yet a hosted CI gate.
VS Code's **Run Tests with Coverage** requires `pytest-cov`, installed by the
locked development setup. Its selected interpreter must be `.venv/Scripts/python.exe`.
Selecting only some tests may miss the threshold; use all focused test modules in the command above
for the recording/service gate. The editor may choose its own collection source;
the CLI command above preserves the configured source directory by using `--cov`
without a value.
Do not exclude `NotImplementedError` lines to improve results. Current coverage
measures snapshot validation, numerical preparation, sample access, partial
recalculation, service state, subscription delivery and revision/error handling.
Behavior tests establish these contracts separately from the coverage percentage;
coverage alone does not qualify physical interpretation or UI integration. As implementation adds
branches, behavioral tests must cover those paths without weakening the threshold.

## Test design

Test each responsibility at its own boundary. Keep exhaustive cheap cases for
parser errors, numerical edges, source preservation and translation placeholders.
Check layout geometry, glyph bounds and alpha directly in rendered frames for
every supported layout/aspect. Test video-rate mapping independently of repeated
full-frame rendering.

GUI loading covers Manta with gravity/GPS and Iron Gwazi without those sensors.
Shared zoom, wheel and selection interactions run once with Manta; fixture-wide
import and scientific contracts remain in their dedicated suites. Full imports
check all five originals once; adapter equivalence, repeatability and concurrent
ownership use one recording rather than repeating the complete fixture matrix.
Export-dialog, palette and language interaction tests use 8 × 8 renderer test
frames while keeping actual preview workers, compositing and UI updates. Dedicated
rendering/preview tests and the two native 4K scaling checks retain real frames.
This separation keeps interaction tests small without reducing production-frame
coverage. Timing comparisons and individual test-run logs belong in `.tmp/`.

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

## Documentation checks

Install the locked Node tools through [Windows setup](SETUP.md), then run:

```powershell
npm run test:docs
```

The suite works offline and combines `lint:docs`, `spellcheck` and
`test:docs:links`; each can also run separately. It does not modify files or fetch
external targets. [CI selection](CI.md) defines when the documentation job runs.

### Scope and limitations

| Check        | Configuration / behavior                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Markdownlint | `.markdownlint-cli2.jsonc`: root Markdown, `docs/`, `.github/` and `.agents/skills/`; default rules except MD013/MD036, aligned MD060 tables; respects Git ignores |
| CSpell       | `.cspell.json`: English, case-insensitive language settings and bundled Python dictionary; shared with VS Code; checks configured code/docs/configuration patterns |
| Local links  | `tests/docs/documentation.test.mjs`: markdown-it parses links/images in root/docs/GitHub/skill Markdown; targets must exist inside the repository                  |

CSpell excludes environments, dependencies, temporary/build outputs, lock files
and `.forces`. Correct spelling errors; add only legitimate project/tool names.
Link tests resolve relative paths from each document and leading slashes from the
repository root. They skip links inside code, external URLs, query strings and
heading fragments; they verify neither external availability nor anchor spelling.
Fixture links check existence without parsing or modifying recordings.

Recommended VS Code extensions consume the same Markdown/CSpell configuration.
CLI success does not establish interactive editor feedback or Mermaid rendering.
Changed Mermaid definitions require a separate syntax check; report visual limits.

## Primary references

- [Pydantic configuration](https://docs.pydantic.dev/latest/concepts/config/) and
  [mypy integration](https://docs.pydantic.dev/latest/integrations/mypy/).
- [Ruff editor settings](https://docs.astral.sh/ruff/editors/settings/).
- [Pylance/Pyright configuration](https://github.com/microsoft/pylance-release/blob/main/USING_WITH_PYRIGHT.md).
- [Qt widget size](https://doc.qt.io/qt-6/qwidget.html#QWIDGETSIZE_MAX).
