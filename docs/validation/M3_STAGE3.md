# M3 Stage 3 — Frame mathematics and capability gates

<!-- cspell:words orthonormal linalg orthogonalization -->

2026-10-17 · Local branch `chore/workspace-setup-and-docs`, base
`4b201c42adb8201882bc9c91483ca03124290a57`, plus earlier owner-reviewed staged
workspace/docs changes and the Stage 3 working-tree scope described below.
**Scope:** SCI-003/007–009, VAL-001–002, partial AC-01/04 and ARC-001–004.
The local Stage 3 numerical-math/capability-gate exit is verified. This is a stage
report; the reduced milestone is complete under [current acceptance](M3.md).

## Delivered behavior and scientific limits

`analysis.frames` implements explicit OrthonormalFrame, rotate_vectors,
RiderCalibration and analyze_rider_frame. Basis rows are target axes in DEVICE
coordinates; passive `v_target = R @ v_device`, inverse transpose conversion,
orthogonality and determinant +1 are checked. Admission uses absolute `1e-10`,
relative zero; synthetic numeric comparisons use `1e-14`. These are numerical
thresholds, not empirical source-app tolerances. Invalid/scaled/skewed/reflected
bases are rejected without normalization, missing axes or SciPy repair.

A source-bound calibration plus matching independent unit/quantity contracts,
explicit rider_calibrated provisional permission and named assumptions yields
PROVISIONAL vectors only. Missing qualification/data produces UNAVAILABLE;
range defects yield INVALID products. Caller misuse raises. Source, time basis,
indices, original unit/quantity declarations, basis/references, assumptions and
library versions remain retained. No verified real rider loading is exposed.

[ADR 0005](../decisions/0005-passive-frame-transforms.md) records the numerical
convention and refreshed primary references. Ride Forces editing/force guidance
confirms calibration/selection matter but supplies no version-matched export-axis
mapping. Source-app screens support the separate [app-reference contract](APP_REFERENCE.md);
controlled mounting evidence and general physical frame mapping remain open. ADR 0003 policy review is still open; correct synthetic math is not
empirical calibration. No unit/sign/yaw/epoch or end-index meaning was inferred.

All five original Path imports retained exact bytes/SHA-256/mtime and produced no
available rider channel by default. Directly inspecting their longitudinal/lateral/
vertical direction vectors in that candidate row order fails the strict numeric
admission policy in every file. That order is an inspection hypothesis, not an
exporter contract or a claim that recordings are corrupt. Original vectors and
calibration markers remain intact; Watch gravity/GPS are never fabricated.

## SciPy adoption and compatibility

LIB-002 requires SciPy rotations. The owner-instructed stage adopts SciPy 1.18.1
exactly in the optional analysis extra; locked NumPy stays at 2.5.4 and other
existing versions are retained. Root lock resolves 37 packages. Native CPython
3.14.6 Windows x64 downloaded/installed the cp314 Windows wheel; no source build.
PyPI reports Python >=3.12 and no listed vulnerabilities for that release on the
check date. This is a dated metadata observation, not a complete security scan.
Installed `scipy-1.18.1.dist-info/LICENSE.txt` includes BSD and bundled
OpenBLAS/LAPACK/GCC notices; full redistribution review remains a release task.
GeographicLib, filtering and interpolation are not adopted or implemented here.

## Native Windows commands and results

Environment: native Windows x64, Python 3.14.6 / pytest 9.1.1,
NumPy 2.5.4 / Pint 0.26.1 / SciPy 1.18.1, PySide6/Qt 6.12.0,
uv 0.13.0 and Node 26.11.1 / npm 11.20.0. Commands run from repository root
through cmd/Windows PowerShell; runner scripts/logs remain in `.tmp/stage3-*`.

- `uv add --optional analysis scipy==1.18.1 --no-sync` and
  `uv sync --locked --all-extras --group dev`: passed; 37-package lock,
  local editable rebuild and SciPy added without upgrading other packages.
- `.venv\Scripts\python.exe .tmp\stage3-audit.py` and
  `.venv\Scripts\python.exe .tmp\stage3-license.py`: checked release/wheel/license
  evidence and all five unchanged source fixtures; details in `.tmp/stage3-audit.json`.
- `uv run --locked pytest tests/test_frames.py tests/test_device_analysis.py tests/test_analysis_models.py`:
  final **80 passed in 8.18 s**, including 21 new frame cases (initial focused run:
  80 passed in 7.97 s).
- `uv run --locked pytest`: **916 passed in 41.93 s**, including native GUI and
  all fixture guards. After the final runtime type-guard/test-helper corrections,
  the affected 80 analysis tests were rerun as above. The other 836 cases retain
  valid evidence: their executable dependencies and the 37-package environment
  are unchanged. Later spelling annotations change comments only.
- `uv lock --check`: consistent 37-package lock.
- `uv run --locked ruff check .`: passed. `uv run --locked ruff format --check src tests`:
  43 files formatted. `uv run --locked mypy src`: no issues in 25 source files.
- `npm run typecheck`: zero errors/warnings. `npm run test:types`: 11 passed.
  `npm run test:dependencies`: 15 passed. `node --test tests/ci/changes.test.mjs`: 40 passed.
- Separate tool checks, because Python manifest/lock inputs changed:
  `uv run --locked ruff check .agents/skills/github-delivery` and
  `uv run --locked ruff format --check .agents/skills/github-delivery` passed (3 files);
  `uv run --locked mypy .agents/skills/github-delivery/scripts/git_delivery.py .agents/skills/github-delivery/tests/test_github_delivery.py`
  passed (2 files); `uv run --locked pytest .agents/skills/github-delivery/tests`:
  **81 passed in 61.24 s**. These are separate from application discovery.
- `.tmp/node-v26.11.1-win-x64/node.exe .tmp/stage3-mermaid.mjs`: all **8 Mermaid
  definitions passed** syntax checks with isolated Mermaid 12.2.0 and a DOM adapter.
  The first runner needed a DOM implementation for Mermaid's sanitizer; the
  diagram text was not altered to work around that runner error.
- `npm run test:docs`: **57 local-link tests passed**, Markdownlint checked 57
  documents and CSpell checked 121 files, both with zero issues. Final report edits
  receive the same suite again; unchanged executable checks are reused.
- `git diff --check`: passed. No fixture working-tree differences were found.
  Earlier file-local spelling corrections changed comments only; final Ruff lint
  and format checks also passed afterward. No global dictionary/check rule changed.

## Traceability and remaining acceptance

- SCI-003/007–009 and VAL-001–002: explicit passive/inverse convention, basis
  validation and analytic positive/negative/inverted/non-axis-aligned tests;
  gravity alone supplies no yaw, and no source direction is automatically assigned.
- SCI-001/002/010–012 and RES contracts: full M2 input, retained provenance,
  source binding, independent motion/unit gates, explicit missingness and immutable output.
- AC-01/04: numerical/frame-gate evidence is stage-scoped. Independent source
  generic physical calibration remains deferred; this evidence is not proof of
  planned selected-range extrema or final reduced-M3 acceptance.
- ARC-001–003: updated existing arc42 views and linked ADR 0005; syntax check covers
  the changed block diagram. Visual/hosted rendering remains unverified. ARC-004
  and complete reduced-M3 acceptance require the current plan
  and a final M3 report.

This frame report does not verify source-app runtime, new originals, clean VM/ARM64,
GPS geodesics, statistics, GUI or hosted CI. Explorer/reference behavior has
separate evidence and does not complete the frame qualification gate.

Current acceptance is defined by the [reduced M3 requirements](../requirements/DEV-REQ-003-scientific-analysis.md)
and [plan](../implementation/DEV-REQ-003/PLAN.md). This report verifies its recorded
API scope; it does not establish planned extrema or final reduced-M3 acceptance.
General physical qualification and GPS analytics are not completion prerequisites.
