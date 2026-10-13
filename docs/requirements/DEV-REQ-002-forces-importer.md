# DEV-REQ-002 — Ride Forces file importer

**Milestone:** M2 | **Status:** Proposed specification, implementation not started
**Target:** Windows, Python 3.14.6 | **Source format:** Ride Forces `.forces`
**Scope authority:** [Roadmap](../ROADMAP.md), [architecture](../architecture/OVERVIEW.md), [recordings](../development/RECORDINGS.md), [AGENTS.md](../../AGENTS.md).

## 1. Purpose and boundaries

Implement an offline, read-only, version-aware importer converting exported Ride Forces JSON
recordings into a typed, immutable canonical representation suitable for subsequent analysis,
storage, visualization and video export. All original information must remain recoverable
without writing to or normalizing the source file. Supported initial corpus: Manta, Kraken,
Taron and Voltron Nevera in `tests/fixtures/real/`; each is owner-authorized and SHA-256-pinned.

**Out of scope:** Force projection and calibration math (M3), GUI explorer (M4),
playback (M5), external CSV/JSON/video export (M6), synchronized POV video (M7),
SQLite ride-library implementation (M4 or a separately approved change), proprietary
format reverse-engineering beyond observed evidence, and changes to the recording files.

The source export schema is not a published contract. Distinguish **observed** behavior
from importer **policy** and **unverified** scientific interpretation throughout.

## 2. Evidence-based schema inventory

Complete baseline observations are recorded in
[FORMAT-ANALYSIS.md](FORMAT-ANALYSIS.md). All four samples use
`schemaVersion = "2.2.0"`, `device = "iPhone"`, `advancedRecording = true`.
Every sample has `accelerationSequence`, `gravitySequence`, `locationSequence`,
direction/calibration vectors, sample rate, indexing metadata, attributes and extrema.
Some fields appear only in certain files: `location`, `ridingPosition`, and all
five weather fields. Vector components in the acceleration sequence are decimal
**strings**, not JSON numbers. GPS timestamps are JSON numbers. JSON object member
order varies and has no semantic meaning. Source `date` and GPS `timestamp` epoch
are not established; do not label them Unix timestamps without proof.

## 3. Canonical importer contract

### 3.1 Public API

- **FR-001:** Provide a side-effect-free public entry point such as
  `import_forces(path: Path) -> ImportResult` and a bytes-based entry point for
  synthetic fixtures. Use a separate path/IO adapter and pure parse/validation functions.
- **FR-002:** Define typed immutable models for `Recording`, `Vector3`,
  `MotionSequence`, `GpsFix`, `Attribute`, `RecordingMetadata`,
  `SourceEnvelope`, `ImportDiagnostic`, and `ImportResult`. Names may be adjusted
  by an ADR, but each concept and contract must be represented.
- **FR-003:** `ImportResult` exposes success/failure, diagnostics, schema version,
  original byte count, source SHA-256 and a fully typed recording on success. Never
  return partially valid measured arrays disguised as complete success.
- **FR-004:** Keep raw source bytes or a byte-for-byte stable immutable reference
  to the local original plus its hash. Preserve the entire source tree including unknown
  fields, original number/string distinctions and optional properties. A normalized
  domain view is **additional**, not a substitute for the source envelope.
  Demonstrate exact byte round-trip where an in-memory envelope is used.
- **FR-005:** No mutation of the input path; do not alter file timestamps, names or
  bytes, and never write imported content back to `.forces` files.
- **FR-006:** Preserve source indices, calibration vectors, source extrema,
  `smoothingFactor`, `attributes`, GPS accuracy fields, `ridingPosition`,
  weather and date values verbatim in the source envelope. Parsed accessors may
  expose numeric values without overwriting the source values.

### 3.2 Schema version and fields

- **FR-007:** Recognize initial schema version `2.2.0` explicitly. Unsupported
  future/older versions must yield a structured `UNSUPPORTED_SCHEMA_VERSION`
  result rather than silently applying version 2.2.0 semantics. An opt-in inspection
  mode may expose safe metadata, but must not report successful supported import.
- **FR-008:** The minimum required fields for a *supported full recording* are
  `schemaVersion`, `accelerationSequence`, `gravitySequence`, `sampleRate`,
  `startIndex`, `endIndex`, and every `x/y/z` component in each motion sample.
  Other fields are retained and classified based on their role; direction/calibration
  vectors, source metadata, UUID, GPS and markers can be missing without destroying
  a raw-motion-only recording, with explicit diagnostics. Do not claim such incomplete
  recordings are eligible for M3 rider-axis analysis.
- **FR-009:** Model `location`, `ridingPosition`, `temperature`,
  `weatherConditions`, `windDirection`, `windSpeed`, `windGust` and optional
  `attributes` as optional. Never synthesize a missing location from GPS or infer
  riding position from a ride's name.
- **FR-010:** Unknown top-level and nested fields must survive intact and be available
  to future versions. Do not reject otherwise valid supported recordings for extensions.
  Optionally issue an informational `UNKNOWN_FIELD_PRESERVED` diagnostic.

### 3.3 Numbers, sequences, and indices

- **FR-011:** Parse finite decimal numeric strings in x/y/z motion and vector fields;
  accept finite JSON numbers if semantically compatible. Reject booleans, nulls,
  nonnumeric tokens, NaN/Infinity, excess malformed members and non-finite results
  with path-specific diagnostics. Do not silently coerce invalid values to zero.
  Retain the source spelling in the source envelope.
- **FR-012:** Validate `sampleRate` as a positive, finite numeric value and keep its
  exact source value. Do not hard-code 50 Hz; all four baseline fixtures happen to use 50.
  Recording sample time may be derived as an **explicit provisional** `i / sampleRate`
  coordinate only if no per-sample time exists; label this as inferred, not measured.
- **FR-013:** Validate motion sequences as arrays and ensure nonempty acceleration
  samples. Detect sequence length mismatch, missing vectors or defective components.
  Decide/document whether a mismatch is fatal for fully paired recordings; baseline
  implementation must treat it as a fatal structural error, not truncate or pad data.
- **FR-014:** Validate `startIndex` and `endIndex` as integer, non-boolean,
  within `[0, N-1]`, with `startIndex <= endIndex`. Treat the inclusive/exclusive
  interpretation of the end index as **unverified**, retain original values and
  use no implied slicing in M2.
- **FR-015:** `gravityIndex` and `inclineIndex`, when present, must be integers
  within the sequence bounds, but need not lie inside the start/end interval or be
  chronologically ordered relative to start/end. Preserve exactly.
- **FR-016:** Validate optional `Vector3` objects structurally, avoiding assumptions
  about axes, handedness, polarity, calibration rotation or normalization. Invalid
  optional vectors should produce a diagnostic and an unavailable typed accessor,
  while preserving source bytes. Never calculate rider G forces during import.
- **FR-017:** Import all `attributes` records as an ordered list of typed
  label/id/value accessors with their original representations retained. No fixed
  count or fixed label vocabulary is permitted; Taron contains both Row and Seat.
  Malformed optional attribute entries get targeted warnings without corrupting
  the remaining entries.

### 3.4 GPS and metadata

- **FR-018:** Preserve the GPS sequence independently of the accelerometer sequence;
  no 1:1 sample alignment, resampling or speed-unit conversion in M2.
- **FR-019:** Recognize coordinates, altitude, `timestamp`, `speed`, `course`,
  `horizontalAccuracy`, `verticalAccuracy`, `speedAccuracy`,
  and `courseAccuracy` as potentially available fields.
  Missing optional members become absent/unknown, not invented values.
- **FR-020:** Preserve negative `speed`, `course` and accuracy measurements
  **verbatim**. Emit a semantic warning when an apparent negative sentinel occurs;
  do not present a negative speed as a physically validated ride speed. Sentinel
  meanings and GPS units remain unverified pending M3/source-app research.
- **FR-021:** Do not reject suspicious but finite GPS positions, precision,
  reported accuracy, or timestamp ordering solely due to heuristic thresholds;
  produce contextual warnings. Reject malformed JSON types for required GPS
  coordinates of a fix only at the fix level, retain original bytes, and make
  it clear whether a GPS fix is unavailable or an entire import failed.
- **FR-022:** Retain the original `date`, `timezone`, latitude/longitude and
  all other metadata. The epoch of numeric `date` is not verified: do not
  convert it to a display date without an explicit separately validated policy.

### 3.5 Diagnostics and error handling

- **FR-023:** Use structured `code`, `severity` (`error`, `warning`,
  `info`), `json_path`, human-readable message, and optional sample index.
  Diagnostics order must be stable for identical input.
- **FR-024:** Fail safely and predictably for nonexistent files, unreadable paths,
  empty input, invalid UTF-8, malformed JSON, duplicate JSON keys, root non-object,
  unsupported version, invalid required fields, arrays too large for configured
  limits, and oversized files. Never use `eval` or deserialize executable objects.
  Set conservative configurable resource limits, document defaults and test them.
- **FR-025:** Optional-field defects become warnings and unavailable typed values
  if the core motion data remains usable. Severe structural corruption must never
  be silently turned into valid zero-filled samples.
- **FR-026:** No implicit network requests, telemetry, location lookups or uploads.
  Display and log errors without reproducing entire GPS traces or sensitive payloads.
- **FR-027:** Imported models must not mutate when callers modify their inputs
  or source JSON; use copying/immutable containers or clearly controlled accessors.

### 3.6 Integration and performance

- **FR-028:** Integrate importer through the existing `importers` and `domain`
  boundaries and supply a minimal non-GUI callable integration surface. Do not
  put validation into Qt widgets or implement M4 GUI behavior.
- **FR-029:** Support repeated deterministic import of all four real fixtures
  under the locked Windows development environment. Document representative
  memory/time measurements without enforcing invented performance guarantees.
- **FR-030:** Provide unambiguous API documentation, version policy,
  field coverage, warning definitions and a later-versions extension recipe.

## 4. Non-functional requirements

- **NFR-001 Integrity:** Existing fixture SHA-256 and length tests remain unchanged
  and pass; original files remain byte-identical before/after every test.
- **NFR-002 Determinism:** Same bytes + version policy -> equivalent typed output
  and ordered diagnostics.
- **NFR-003 Security:** Strict JSON parsing, bounded input, no code execution,
  no secrets or coordinates in CI logs, offline-only operation.
- **NFR-004 Maintainability:** Type-checked, layered Python 3.14.6 design,
  explicit version adapters, tests without Qt, no redundant new dependency.
- **NFR-005 Backward resilience:** New optional fields do not destroy data;
  supported-version schema drift is diagnosed and documented.
- **NFR-006 Developer workflow:** Dedicated branch from `main`, explicit owner
  approval for commits/pushes and PR merge, tests and docs per `AGENTS.md`.
- **NFR-007 Traceability:** Link every test group and implementation phase to
  requirement identifiers; M2 sign-off cannot rely on CI status alone.

## 5. Test catalog and acceptance criteria

| ID    | Acceptance test                                                                                                                                                |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC-01 | All four actual recordings import successfully under schema 2.2.0 with their full motion/GPS arrays and metadata; note warnings without data loss.             |
| AC-02 | Original byte lengths and SHA-256 remain identical across before/after import, including all original GPS data.                                                |
| AC-03 | Tests demonstrate JSON source round-trip, unknown-field preservation, original numeric-string representations and no file write.                               |
| AC-04 | Missing optional park, riding-position and weather fields do not fail import; multiple attributes remain ordered.                                              |
| AC-05 | Invalid required fields, malformed UTF-8/JSON, duplicate JSON keys, unsupported version and resource-limit violations produce deterministic structured errors. |
| AC-06 | Numeric string parsing, non-finite value rejection, sample lengths, index bounds and no assumed marker ordering are tested.                                    |
| AC-07 | Negative GPS sentinels remain intact with warnings; GPS fields are not fabricated, aligned to motion samples or assumed to have verified units.                |
| AC-08 | Public typed API is Qt-independent and documented; repeat imports are deterministic.                                                                           |
| AC-09 | Focused importer tests and the required Ruff, mypy, Pyright, pytest, documentation and lock checks pass on native Windows.                                     |
| AC-10 | A dedicated PR verifies both GitHub CI jobs, and a dated M2 validation report records evidence and remaining limitations.                                      |

**Do not mark M2 complete** until all criteria have demonstrable evidence.
Record unresolved GPS, force and time semantics for M3 without inventing answers.

## 6. Open questions and design decisions

| ID    | Issue                                                           | Policy until verified                                                            |
| ----- | --------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| OQ-01 | Numeric `date` / GPS `timestamp` epoch                          | Preserve as numbers, no Unix conversion.                                         |
| OQ-02 | Inclusive/exclusive `endIndex` semantics                        | Preserve and validate bounds only.                                               |
| OQ-03 | Calibration/direction meaning and units                         | Preserve; no M2 force projections.                                               |
| OQ-04 | Meaning of negative GPS speed/course/accuracy                   | Preserve and flag, no unit claims.                                               |
| OQ-05 | Unpublished future schema variants                              | Reject as unsupported for full import; retain source inspection separately.      |
| OQ-06 | Resource size limits, invalid optional GPS fix handling         | Document detailed defaults and tests in implementation ADR before parser coding. |
| OQ-07 | Future per-sample timestamps or altered sample-rate conventions | Detect extension fields, never silently assume alignment.                        |

## 7. Implementation references

See [implementation plan](../implementation/DEV-REQ-002/PLAN.md),
[sequential Codex prompts](../implementation/DEV-REQ-002/PROMPTS.md) and
[observed format analysis](FORMAT-ANALYSIS.md). M2 is documentation-only
until an explicit separate implementation instruction is given.
