# Code quality and validation

[Windows setup](SETUP.md) owns installation and canonical check commands;
[AGENTS.md](../../AGENTS.md) governs evidence reuse.
Architecture owns [platform constraints](../architecture/02_architecture_constraints.md)
and [quality goals/acceptance boundaries](../architecture/10_quality_requirements.md).
Installed checks work offline.

## Python inline documentation

Application and tool code use English Google-style documentation strings. Test code is exempt.
Public functions and methods describe their purpose, parameters in `Args`, results
in `Returns` or `Yields`, and expected exceptions in `Raises`. Describe units,
missing values and side effects where they affect the contract; type annotations
remain the source of parameter and return types. Class documentation describes stored
fields in `Attributes`. Comment local variables only when their purpose or the
reason for a calculation is not clear from the code.

## Runtime and static contracts

| Contract                     | Validation                                                                                                                                                               |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `runtime.config.AppSettings` | Immutable, strict Pydantic model; validated defaults; rejects unknown keys, empty titles, type coercion and dimensions outside 1–16,777,215 (Qt widget limit)            |
| Preferences                  | Declared language/appearance choices; boolean update consent; finite numeric timestamps; string tags; `Path` directory inputs; supported export frame rates; no coercion |
| Persistence                  | Invalid setter inputs raise `ValueError` before writes; statically restricted keys; SQLite text values; invalid stored values/unavailable storage use safe defaults      |
| Source/analysis models       | Separate owned frozen dataclasses; [source contracts](CANONICAL_MODELS.md) and [analysis contracts](ANALYSIS_MODELS.md)                                                  |

| Tool            | Configuration and limits                                                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Ruff            | `pyproject.toml`: Python 3.14, 100 columns, `F`/`COM812`, LF, magic trailing commas; format checks report drift without rewriting; COM812 is intentional                 |
| mypy            | Strict `src/` checks; Pydantic typed-constructor plugin                                                                                                                  |
| Pylance/Pyright | Shared strict Windows Python 3.14 configuration for `src/` and `tests/`, excluding dependencies/caches; CLI engine lock-pinned, potentially different from editor engine |
| VS Code         | `.vscode/settings.json`: selected Windows interpreter, locked Ruff executable, format on save, explicit-save fixes; interpreter selection in setup                       |

CLI success does not verify editor feedback.

## Test coverage

Python suites: `tests/<subsystem>/test_<behavior>.py`. Behavior names and subsystem
folders identify scope; no additional marker matrix is required.

| Directory                        | Responsibility                                                                    |
| -------------------------------- | --------------------------------------------------------------------------------- |
| domain                           | Source ownership and immutable recording models                                   |
| importers                        | Decoding, motion, optional fields, diagnostics and Path/bytes import              |
| analysis                         | Models, device/frame math, source references, context/events, service and extrema |
| explorer                         | Qt-independent presentation, selections and GPS geometry                          |
| rendering                        | Frames, layouts, previews, encoding, progress, estimates and batches              |
| storage                          | Persistent application preferences                                                |
| localization                     | Translation catalog, overlay text and OS language defaults                        |
| ui                               | Native Qt startup, explorer, dialogs, appearance and interactions                 |
| updates                          | Release discovery, transport and update preferences                               |
| recordings                       | Original fixture hashes and recursive schema inventory                            |
| fixtures                         | Data only: original recordings and recursive schema inventory                     |
| packaging                        | Release policy, source archives and native Windows/Linux/macOS packages           |
| tooling                          | Application settings/version and Ruff contracts                                   |
| support                          | Fixture paths, pinned identities and inventory helper                             |
| types / dependencies / ci / docs | Separate Node type, dependency, CI and documentation checks                       |

- Run a subsystem/file directly: `uv run --locked pytest tests/importers` or
  `uv run --locked pytest tests/ui/test_export.py`.
- Type-contract tests require analyzed files and expected diagnostic rules, not
  merely an exit code. Node suites are development tooling, not rendering;
  [dependency policy](DEPENDENCIES.md#node-overrides-and-security-boundary) owns
  override rationale/security limits.
- `tests/importers/benchmark.py` measures time/Python allocations without performance
  assertions. Source tests preserve bytes and scientific unknowns; synthetic
  numerical success does not qualify real sensors.
- Fixtures: shared synthetic data in `tests/conftest.py`; GUI/preference isolation in
  `tests/ui/conftest.py`; waits/workspace sizing in `tests/ui/helpers.py`;
  recording identities in `tests/support/recordings.py`; originals in `tests/fixtures/`.
  Rendering reference data: `tests/rendering/conftest.py`. Each UI test isolates
  `LOCALAPPDATA`, including preference/export databases and subprocesses; no second
  export database-path override is needed.
- Developer-tool regressions under `.agents/skills/` are outside application
  discovery; [skill instructions](../../.agents/skills/github-delivery/SKILL.md)
  define execution scope. [CI selection](CI.md) owns job selection.
- [Source-app evidence tests](../../tests/analysis/test_source_app_evidence.py)
  use unified snapshots and independent source-file/screenshot expectations.
  Projection/filter tests remain separate from model/service integration.

Reference generators and source-entry smoke checks run through actual entry points:

```powershell
uv run --locked pytest tests/rendering/test_reference_script.py tests/ui/test_reference_screenshots.py tests/packaging/test_windows_smoke.py
```

Outputs stay in `.tmp/`; fixtures remain unchanged and personal preferences isolated.
Source smoke checks do not replace [frozen-package qualification](RELEASE.md#windows-packages).

## Coverage gate

Locked `coverage.py`/`pytest-cov` measure lines and branches throughout `analysis`,
`validation`, `storage`, `i18n`, `formatting`, `playback`, `runtime`, `gps` and
`domain`. `[tool.coverage.*]` in `pyproject.toml` owns configuration.
Subprocess measurement includes isolated error-report lifecycle and exception-hook tests. Collection selects the declared sources without importing modules for discovery. Run from the repository root on native Windows:

```powershell
uv run --locked pytest --cov --cov-report=term-missing `
    tests/analysis tests/tooling/test_validation.py tests/storage `
    tests/rendering/test_batches.py tests/rendering/test_analysis_snapshots.py `
    tests/updates/test_releases.py tests/localization `
    tests/explorer/test_data.py::test_replay_sample_counter_format tests/playback `
    tests/support tests/tooling/test_runtime_paths.py tests/tooling/test_settings.py `
    tests/explorer/test_gps.py tests/explorer/test_map_background.py tests/domain
uv run --locked coverage html
uv run --locked coverage json
```

| Rule        | Contract                                                                                                                               |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Gate        | Test success and configured 100% coverage; each reported module fully covered                                                          |
| Measurement | Replaces previous data; no append; `coverage report` can check existing data                                                           |
| Outputs     | `.tmp/coverage/analysis/`: data, `html/index.html`, `coverage.json`                                                                    |
| Execution   | Separate from ordinary pytest; not a hosted CI gate                                                                                    |
| VS Code     | **Run Tests with Coverage** requires locked `pytest-cov` and `.venv/Scripts/python.exe`; partial test selection can miss the threshold |
| Collection  | CLI `--cov` without a value preserves configured source directory; editor may choose another source                                    |

Analysis coverage includes models, device and rider frames, calibration, projection,
smoothing, orientation, extrema, airtime/events, snapshot preparation and partial
recalculation, service state, subscriptions and revision/errors.
Storage coverage includes preferences and recording markers, immutable export
definitions, transactional preset/batch persistence and the bounded map-tile cache.
Localization coverage includes both translation catalogs, deferred text rendering,
language selection, numeric formatting and diagnostic fallbacks. Shared replay-time
formatting covers sample counters, negative offsets and fractional sample rates.
Playback coverage checks the clock, speed changes, seeking, pause/resume and
recording boundaries independently of Qt. Runtime coverage includes bootstrap
settings, platform paths, CPU topology, support diagnostics, bounded release lookup,
instance locking and local-socket requests, exception forwarding and report cleanup.
Platform fallback branches use controlled test doubles on Windows; they do not
replace native Linux/macOS package qualification. GPS coverage checks route gaps,
projection, bounded viewport requests, HTTP/cache rules and cancellation using
simulated tile responses without live network access. Domain coverage includes
immutable source ownership, exact number tokens, constructor type checks and
recording-component consistency without decoding or rewriting original recordings.
Behavior tests establish contracts; coverage percentage does not qualify physical
interpretation or UI integration. Cover new branches without weakening the gate.

## Test design

- Put exhaustive parser, numerical-edge, source-preservation and translation cases
  at their inexpensive subsystem boundaries.
- Reuse a loaded recording/window for related GUI assertions. Reset view state
  between variants; use separate processes/windows only for lifecycle or isolation risks.
- Keep full-resolution geometry, glyph and alpha checks in rendering suites.
  GUI workflow tests can use small frames while exercising real worker transport.
- Exercise real encoders with representative codecs, layouts, aspects and backend
  preferences. Keep command-contract and numerical timing tests independent.
- Verify ordered/bounded parallel frames, worker ownership, cancellation and cleanup.
  Batch tests distinguish queue behavior from per-frame parallel rendering.
- Isolate preferences and output under `.tmp/`; never use personal application state.
  Logs and timing observations belong there, not in tracked test histories.

Desktop layout references model a 3840 × 2160 editing display:

| Scaling | Logical working area, reserving taskbar space | Use                                                             |
| ------- | --------------------------------------------- | --------------------------------------------------------------- |
| 150%    | 2560 × 1400                                   | Export layouts with EN/DE/FR text                               |
| 200%    | 1920 × 1040                                   | Shared interactions and export layouts with EN/DE/FR text       |

These are test-controlled Qt client sizes, independent of the physical monitor.
Native startup separately checks actual desktop constraints. Video resolution and
aspect tests are independent of desktop size; CI layout checks do not establish
visual acceptance on a physical 4K display.

## Documentation checks

Install locked Node tools through [Windows setup](SETUP.md):

```powershell
npm run test:docs
```

Offline combination of `lint:docs`, `spellcheck` and `test:docs:links`; each also
runs separately. No file modification or external-target fetching.
[CI selection](CI.md) defines job selection.

### Scope and limitations

| Check              | Configuration / behavior                                                                                                                                        |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Markdownlint       | `.markdownlint-cli2.jsonc`: root Markdown, `docs/`, `.github/`, `.agents/skills/`; default rules except MD013/MD036, aligned MD060 tables; respects Git ignores |
| CSpell             | English default, German/French catalog overrides; case-insensitive settings and Python dictionary; shared CLI/VS Code configuration                             |
| Local links        | `tests/docs/documentation.test.mjs`: markdown-it parses root/docs/GitHub/skill Markdown links/images; targets must exist inside the repository                  |
| Website navigation | Same test file checks layout navigation against README level-two headings                                                                                       |

- CSpell excludes environments, dependencies, temporary/build outputs, locks and
  `.forces`. Correct errors; add only legitimate project/tool names.
- Link paths resolve relative to documents; leading slashes resolve from repository
  root. Code and external URLs are skipped; query strings/fragments are stripped.
  External availability and general anchor spelling are not checked.
- Fixture links check existence without parsing/modifying recordings.
- Recommended editor extensions share Markdown/CSpell configuration. CLI checks
  do not verify editor feedback or Mermaid rendering. Changed Mermaid definitions
  need separate syntax validation; visual limits remain explicit.

## Primary references

- [Pydantic configuration](https://docs.pydantic.dev/latest/concepts/config/) and
  [mypy integration](https://docs.pydantic.dev/latest/integrations/mypy/).
- [Ruff editor settings](https://docs.astral.sh/ruff/editors/settings/).
- [Pylance/Pyright configuration](https://github.com/microsoft/pylance-release/blob/main/USING_WITH_PYRIGHT.md).
- [Qt widget size](https://doc.qt.io/qt-6/qwidget.html#QWIDGETSIZE_MAX).
