# Sequential Codex prompts — DEV-REQ-003

<!-- cspell:words AHRS stationarity Butterworth Goldens orthonormality acausal Missingness sosfiltfilt basemaps -->

**Status:** Future implementation guidance, not execution authorization.

Use one prompt per Codex interaction after reviewing the previous stage. The
shared constraints are repeated intentionally to make each prompt standalone.
For final M3 delivery, Prompt 7 must finish acceptance and documentation locally
before any staging, commit, push or draft-PR creation. CI subsequently validates
the published result; it does not finalize local acceptance.

## Prompt 0: 0 — Scientific feasibility

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Inspect the actual M2 code and recording evidence. Produce a scientific ADR covering device specific force vs gravity, units, frame convention, yaw ambiguity, source extrema, GPS epochs, negative sentinels and acceptance of unknowns. Define safe capability gates. No production calculations or dependencies in this step.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Prompt 1: 1 — Library and API design

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Audit library licenses, Windows Python 3.14.6 compatibility and uv lock for NumPy, SciPy, Pint and GeographicLib; treat AHRS and pyproj as optional research only. Design immutable AnalysisResult/AnalysisProfile, diagnostics, typed quantities, frame labels and provenance; do not claim values whose units are unverified.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Prompt 2: 2 — Device vectors and units

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Implement NumPy device-frame norms and explicit Pint quantity conversion only on validated units. Keep gravity and acceleration channels distinct; do not infer the relationship between source fields. Test synthetic stationarity, zero specific-force vector, unit conversion and missing source-unit cases.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Prompt 3: 3 — Rider coordinate mathematics

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Use SciPy Rotation and orthonormality checks to implement tested rotation/projection primitives for synthetic frame data. Do not enable verified rider G outputs unless source-app axes and signs have independent evidence. Test inverses, handedness, axis inversion, degenerate calibration and vector norms.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Prompt 4: 4 — Filtering and statistics

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Implement raw and SciPy SOS zero-phase filtered tracks with explicit cutoff/order/sample-rate settings and short-sequence diagnostics. Add tested extrema, event thresholds, mean, RMS and selected quantiles. Document acausal nature, edge effects and changes to peaks. No hidden defaults.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Prompt 5: 5 — GPS analytical engine

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Implement GeographicLib WGS84 inverse geodesics, horizontal distances and azimuth, configurable fix-quality checks and diagnostics. Preserve source speed and accuracy sentinels; label speed units unknown unless proven; never equate GPS path to track length or time bases without validation.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Prompt 6: 6 — Source comparison

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Develop a reproducible matrix for Manta, Kraken, Taron and Voltron Nevera, preserving original fixture hashes. Compare source minForce/maxForce only when the original app's axis, segment and filtering settings are known; otherwise report unresolved differences without declaring equivalence.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Prompt 7: 7 — Acceptance report

```text
Read AGENTS.md, docs/ROADMAP.md, docs/requirements/DEV-REQ-003-scientific-analysis.md and docs/implementation/DEV-REQ-003/PLAN.md. Confirm verified M2 APIs before coding. All source code, documentation and commit messages must be in English. Respect the existing branch and explicit owner approval gates. Never touch original .forces bytes or silently assume axes, gravity semantics, GPS units or timestamps. Run focused and required checks, report actual evidence, and stop after this single stage.

Specific assignment:
Run exact local Windows validation commands including npm run test:dependencies. Record measured results, numeric tolerances, limits and requirement traceability in docs/validation/M3.md. Verify all AC-01–AC-10 locally, including owner acceptance of any permitted scientific capability exclusion. Finalize the acceptance report and verified roadmap status, then recheck documentation BEFORE staging, committing, pushing or creating the final draft PR. Missing evidence leaves M3 open; documentation or math tests alone are insufficient. Stop with the final local result ready for owner review. Publication requires separate explicit authorization and must already include the final report and status. Subsequent GitHub PR CI is secondary validation and must pass before a separately authorized merge; record hosted outcomes in PR metadata without a completion-only commit. Investigate failures and correct invalidated local acceptance evidence.

Return:
- Changed files and covered DEV-REQ-003 requirement IDs.
- Exact tests executed with results and any failures.
- Unverified scientific assumptions and capability restrictions.
- Proof that original fixture contents were unchanged.
- Next-stage readiness. Do not begin the next stage.
```

## Review criteria

The final M3 draft PR must contain the locally verified acceptance report and
milestone status at creation. Never make either conditional on a future green CI run.

Do not proceed if requirements, reference evidence, type contracts, unit
semantics or tests remain unresolved without an explicit documented exception.
A changed scientific contract requires an approved ADR or requirement revision.
