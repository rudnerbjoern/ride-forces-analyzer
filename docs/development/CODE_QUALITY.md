# Code quality and validation

[Windows setup](SETUP.md) owns installation and canonical check commands;
[AGENTS.md](../../AGENTS.md) governs evidence reuse.
Architecture owns [platform constraints](../architecture/02_architecture_constraints.md)
and [quality goals/acceptance boundaries](../architecture/10_quality_requirements.md).
Installed checks work offline.

## Runtime and static contracts

| Contract               | Validation                                                                                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `config.AppSettings`   | Immutable, strict Pydantic model; validated defaults; rejects unknown keys, empty titles, type coercion and dimensions outside 1–16,777,215 (Qt widget limit)            |
| Preferences            | Declared language/appearance choices; boolean update consent; finite numeric timestamps; string tags; `Path` directory inputs; supported export frame rates; no coercion |
| Persistence            | Invalid setter inputs raise `ValueError` before writes; statically restricted keys; SQLite text values; invalid stored values/unavailable storage use safe defaults      |
| Source/analysis models | Separate owned frozen dataclasses; [source contracts](CANONICAL_MODELS.md) and [analysis contracts](ANALYSIS_MODELS.md)                                                  |

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

## Recording model and service coverage

Locked `coverage.py`/`pytest-cov` measure lines/branches in `analysis.recording`
and `analysis.service`. `[tool.coverage.*]` in `pyproject.toml` owns configuration.
Collection uses the analysis directory without importing modules for discovery.
Run from the repository root on native Windows:

```powershell
uv run --locked pytest --cov --cov-report=term-missing `
    tests/analysis/test_recording.py tests/analysis/test_recording_validation.py `
    tests/analysis/test_recording_preparation.py tests/analysis/test_recording_recalculation.py `
    tests/analysis/test_service.py tests/analysis/test_airtime_events.py
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

Coverage includes snapshot validation, preparation, sample access, partial
recalculation, event integration, service state, subscriptions and revision/errors.
Behavior tests establish contracts; coverage percentage does not qualify physical
interpretation or UI integration. Cover new branches without weakening the gate.

## Test design

Test responsibilities at their own boundaries. Keep exhaustive cheap parser,
numerical-edge, source-preservation and translation-placeholder cases. Check
geometry, glyph bounds and alpha for every layout/aspect; test video-rate mapping
separately from repeated full-frame rendering.

| Scope                                | Representative coverage                                                                                      |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| GUI loading                          | Manta with gravity/GPS; Iron Gwazi without                                                                   |
| Shared zoom/wheel/selection          | Once with Manta; fixture-wide import/scientific cases remain in dedicated suites                             |
| Import ownership                     | Full imports cover five originals once; adapter equivalence, repeatability and concurrency use one recording |
| Export/palette/language interactions | 8 × 8 test frames with actual preview workers, compositing and UI updates                                    |
| Production frames                    | Dedicated rendering/preview suites and two native 4K scaling checks                                          |
| Real encoder                         | Eight codec × aspect × CPU/GPU-preference cases; every layout represented, including German examples         |
| GPU behavior                         | CPU fallback allowed; command-contract tests verify GPU options independently of hardware                    |
| Real batches                         | Two jobs with different rides/formats; pure queue tests cover the ride/preset cross-product                  |
| Progress/cancellation                | Shared GUI flow once; layout controls in existing interaction checks                                         |
| Compact layouts                      | Targeted navigation/scrolling regressions, not another full workflow matrix                                  |

Add variants for distinct risks, without multiplying independent options through
expensive end-to-end workflows. Timing observations/run logs belong in `.tmp/`.

Shared preparation and isolation:

- Source-app screenshot tests prepare each recording once for all independent
  replay references; extrema matrices prepare each window once for raw/calibrated
  views, retaining all recordings/windows/selections.
- Localization/rendering share immutable Manta data per module. Language, patches,
  renderers, settings, derived snapshots and outputs remain test-local. Real 4K
  glyph/language/pixel checks, independent imports and encoder checks remain.
- GPS dialog covers Voltron/Manta replacement and Iron Gwazi removal; pure GPS
  keeps all five recordings. Decoder/motion/optional corpus tests check each
  original value once; service Path/bytes repeatability owns repeated full parsing.
  Concurrent, fresh-process and cheap synthetic guards retain independent setup.
- Same-scene FFmpeg Browse, raw/calibrated click/theme and language/appearance
  variants share a window, retaining assertions and resetting layout and viewport.
  Worker/error and native DPI/startup cases keep separate isolation.
- Arrow tests drive the hold clock before/at thresholds while preserving native
  press, auto-repeat, release and keyboard checks for both fields/directions,
  without repeated five-second holds. CI runs UI serially on its own runner,
  concurrently with non-UI checks; see [CI routing](CI.md).

Desktop layout references model a 3840 × 2160 editing display:

| Scaling | Logical working area, reserving taskbar space | Use                                                             |
| ------- | --------------------------------------------- | --------------------------------------------------------------- |
| 150%    | 2560 × 1400                                   | Export layouts with English/German text                         |
| 200%    | 1920 × 1040                                   | Shared interactions and export layouts with English/German text |

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
| CSpell             | `.cspell.json`: English, case-insensitive language settings, Python dictionary; code/docs/configuration patterns; shared with VS Code                           |
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
