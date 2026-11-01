# Public import service

Public entry points in `ride_forces_analyzer.importers`:

```python
from pathlib import Path

from ride_forces_analyzer.importers import (
    ImportLimits,
    ImportResult,
    import_forces,
    import_forces_bytes,
)


def inspect_recording(path: Path) -> int | None:
    result: ImportResult = import_forces(path, limits=ImportLimits())
    if result.success is True:
        return len(result.recording.motion.acceleration)
    return None


result = import_forces_bytes(b"{}")  # Structured INVALID_SCHEMA_VERSION failure.
```

| API                                                                          | Contract                                                                                           |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `import_forces(path: Path, *, limits=DEFAULT_LIMITS) -> ImportResult`        | Bounded read-only local binary I/O                                                                 |
| `import_forces_bytes(data: bytes, *, limits=DEFAULT_LIMITS) -> ImportResult` | Immutable bytes; no filesystem access                                                              |
| Execution                                                                    | Synchronous, offline, Qt-independent; caller schedules work; no internal thread/progress interface |

Architecture owns [composition](../architecture/05_building_block_view.md#importer-composition-and-interfaces),
[import runtime](../architecture/06_runtime_view.md#read-only-import-and-failures)
and [source ownership](../architecture/08_concepts.md#source-ownership-and-validation).

## Application analysis handoff

- Path imports support `.forces` JSON and `.zforces` Raw-DEFLATE recordings through
  the same validation/analysis path. Bytes-only imports accept uncompressed JSON.
  [Decoding](STRICT_DECODING.md) defines compression limits and original provenance.
- Import success means lossless parsing, not analysis. Import remains usable
  without NumPy/Qt and retains bytes, metadata, unknown fields and independent GPS.
- The application worker supplies `ImportSuccess` and an explicit source-app recipe
  to the analysis service for one immutable snapshot: source/time correspondence,
  projection, smoothing, context/optional events and independent gravity tilt.
- Missing prerequisites yield raw-capable snapshots with coded stage reasons;
  failed imports retain the displayed recording.
- [Analysis API](ANALYSIS_MODELS.md#unified-recording-analysis) owns configuration,
  availability/quality/reuse; [runtime architecture](../architecture/06_runtime_view.md#explorer-analysis-delivery)
  owns workers, subscriptions and guarded success/failure/UI delivery.

## Pipeline and outcomes

[Decode](STRICT_DECODING.md) → [motion](MOTION_PARSING.md) →
[optional data](OPTIONAL_PARSING.md) → immutable `Recording`.
Decode/schema failure stops immediately; core motion failure skips optional parsing.
Optional recovery cannot hide a bad core or produce partial success.
Standalone subset success is not complete-import success.

| Outcome                 | Contract                                                                                                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ImportSuccess`         | `success=True`, typed `Recording`, ordered warning/info diagnostics; `schema_version`, `byte_count`, `source_sha256`                                                                 |
| Retained evidence       | `recording.source.original_bytes` and complete immutable `recording.source.root`; Path provenance retains caller's path, not a mutable file reference; bytes imports use `path=None` |
| `ImportFailure`         | `success=False`, `recording=None`, at least one error; deterministic diagnostics for expected source/I/O/resource defects                                                            |
| Caller misuse           | Wrong argument types raise `TypeError`; invalid limits raise `ValueError` before I/O; programming errors are not source defects                                                      |
| Failure provenance      | Bounded decode/schema/motion/diagnostic failures retain bytes/count/hash where available; malformed JSON may lack a tree, schema failures may retain one                             |
| Incomplete input        | Unreadable/oversized input has no complete source/count/hash; never hash partial reads as complete evidence                                                                          |
| Repeat/concurrent calls | Same input/policy gives equivalent immutable results/diagnostics; each call owns independent tree/recording/diagnostic state; concurrent bytes calls are tested                      |

No process-global decoder/integer/recursion settings change. Changed files are
different inputs; no atomic snapshot or hostile-filesystem race guarantee.

## Field coverage and retained source

| Fields                                                             | Typed view / policy                                                        |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| schemaVersion                                                      | Explicit 2.2.0 or recognized unversioned RFDB profile; no invented version |
| accelerationSequence, gravitySequence                              | All finite vectors; gravity capability may be absent                       |
| sampleRate                                                         | Valid source rate, or owner 50 only for absence with DEFAULT provenance    |
| startIndex, endIndex, gravityIndex, inclineIndex                   | Independently bounded indices; no slicing/marker chronology                |
| Six direction/calibration vectors                                  | Optional structural vectors, no normalization or physical transformation   |
| name, uuid, device, advancedRecording                              | Optional source metadata; device controls expected availability only       |
| date, timezone                                                     | Exact source date number and unconverted timezone text                     |
| location, latitude, longitude                                      | Optional root metadata; no GPS-derived replacement                         |
| ridingPosition                                                     | Source value or Seated only for absence, with explicit provenance          |
| temperature, weatherConditions, windDirection, windSpeed, windGust | Optional weather accessors; no units inferred                              |
| attributes                                                         | Ordered valid entries with arbitrary labels/source values                  |
| locationSequence                                                   | Independent indexed GPS slots and optional finite members                  |
| smoothingFactor, maxForce, minForce                                | Exact SourceNumber accessors; no recalculation                             |
| Any unknown nested/root content                                    | Intact source tree and exact original bytes, including numeric spelling    |

- Absent/invalid attribute containers yield `Recording.attributes=()`; retained
  presence/warnings distinguish these from valid empty arrays. Valid siblings retain order.
- GPS `ABSENT/PRESENT/INVALID` and per-slot `fix=None` remain explicit.
  Acceleration-only Watch success covers available data, not analysis readiness.
- Defaults never enter the source tree. Negative GPS speed/course/accuracy and
  suspicious finite readings remain evidence with warnings, not qualified units/sentinels/speeds.
- Float rounding/underflow never replaces exact tokens. Parsing does not qualify
  coordinates, timestamps/epochs, force units, axes or end-index convention;
  [scientific gates](../architecture/08_concepts.md#scientific-provenance-and-gates) remain applicable.

## Shared diagnostic budget and ordering

| Rule               | Contract                                                                                                                                                                     |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared budget      | One per-call collector for motion/optional errors, warnings and info; enforce `limits.max_diagnostics` during generation, never allocate unbounded diagnostics then truncate |
| Standalone parsers | Same guard, independent per-call budgets                                                                                                                                     |
| Exact limit        | Accepted if no further diagnostic is needed, including motion filling the budget before clean optional parsing                                                               |
| Next diagnostic    | Replace last slot with fatal `RESOURCE_LIMIT_EXCEEDED` at triggering pointer/index; stop, return no Recording                                                                |
| Ordering           | Severity, escaped JSON Pointer, code; stable emission order for exact ties. Core errors may precede the resource error                                                       |
| Decode failures    | Fail-fast single diagnostic, fitting every positive budget                                                                                                                   |
| Unknown content    | Byte/depth/sequence/node/object/string/number limits apply before domain allocation, including unknown fields                                                                |
| Messages           | Identify defects without source values, GPS traces or exception payloads                                                                                                     |

No successful warning set is silently truncated.
[Decoder limits](STRICT_DECODING.md#resource-policy) own defaults/configuration;
budgets are not peak-RAM/throughput guarantees. Motion/optional guides define
warnings; the decoder guide defines whole-document errors.

## Library metadata projection

`importers.library_metadata.project_library_metadata(recording)` returns an immutable
projection of source ride/park names and recording dates. Import itself retains
exact numeric tokens and source text without conversion. The separate
[Library date contract](../requirements/LIBRARY.md#admitted-source-date-contract)
defines the source-evidenced epoch, recording-local day and unknown-date behavior.
It performs no archiving, file writes or UI work.

## Later versions

1. Obtain authorized evidence; inventory schema differences and update the source-contract ADR.
2. Add explicit decoder dispatch and version-specific motion/optional adapters
   before full composition.
3. Add positive/negative bytes/Path/integrity tests; preserve 2.2.0 regressions.
   Reject unknown versions until their full contracts exist; a decoder-map entry alone is insufficient.

## Regression and measurement

```powershell
uv run --locked pytest tests/importers/test_service.py tests/importers/test_motion.py tests/importers/test_optional.py tests/recordings/test_integrity.py
uv run --locked python -m tests.importers.benchmark --repetitions 5
```

Tests cover both adapters, five complete originals, byte equality/arrays/metadata,
repeat/concurrent calls, unknown nesting, decode/aggregate limits, optional recovery,
core failure and fresh-process Qt/network/write guards. Temporary files: `.tmp/`.

| Benchmark property | Boundary                                                                                     |
| ------------------ | -------------------------------------------------------------------------------------------- |
| Platform/integrity | Native Windows; pinned fixture hashes; bytes/modification times checked before/after         |
| Timing             | Per adapter: warmup, five untraced calls, separate traced allocation run; GC outside timings |
| Path versus bytes  | Warm local filesystem reads versus preloaded bytes                                           |
| Tracemalloc        | Python allocations only; excludes preexisting bytes, native allocations and process/OS RAM   |
| Interpretation     | Development measurement, no enforced performance threshold                                   |
