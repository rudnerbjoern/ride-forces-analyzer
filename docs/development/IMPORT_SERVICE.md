# Public import service

The public facade in `ride_forces_analyzer.importers` provides:

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

`import_forces(path: Path, *, limits=DEFAULT_LIMITS) -> ImportResult` uses bounded
read-only local binary I/O. `import_forces_bytes(data: bytes, *, limits=DEFAULT_LIMITS)`
requires immutable bytes and performs no filesystem access. Both are synchronous,
Qt-independent and offline. The raw explorer calls this API through a background
adapter; no UI dependency is added to the service.
The caller controls scheduling; no background thread or progress interface is added.

## Pipeline and outcomes — FR-028–030

The service composes [strict decoding](STRICT_DECODING.md),
[motion validation](MOTION_PARSING.md) and [optional parsing](OPTIONAL_PARSING.md).
Decoder/schema failure stops immediately. Motion failure stops before optional
parsing; optional defects cannot hide a bad core or yield a partial success.
Usable optional fields plus complete available motion form an immutable `Recording`.
Standalone subset APIs remain available but their success is not full import success.

`ImportSuccess` has `success=True`, a typed Recording and ordered warning/info
diagnostics. It exposes schema_version, byte_count and source_sha256. Retrieve
exact input from `recording.source.original_bytes`; the immutable complete source
tree is `recording.source.root`. Path provenance is the caller's Path, not a mutable
file reference; bytes imports have `source.provenance.path=None`.

`ImportFailure` has `success=False`, `recording=None`, at least one error and
deterministic diagnostics. Expected malformed-source/I/O/resource errors are results.
Wrong Python argument types raise TypeError; invalid limit configuration raises
ValueError before I/O. Do not catch arbitrary programming errors and reclassify them
as valid source defects. No process-global decoder, integer or recursion settings change.

Bounded decode/schema/motion/diagnostic failures retain original bytes/hash/count
where available. Malformed JSON may have no source tree; schema failures may retain
a decoded tree. Unreadable/oversized input has no complete source/count/hash.
Never infer a complete-source digest from a partial read. See [import decision](../architecture/09_architecture_decisions.md#source-ownership-and-import).

Repeated same input/policy calls yield equivalent immutable output and diagnostics.
Each call owns independent tree/recording/diagnostic state; concurrent bytes calls
are tested. Files changing between calls are different inputs; no atomic filesystem
snapshot or hostile-filesystem race guarantee is asserted.

## Field coverage and retained source

| Fields                                                             | Typed view / policy                                                        |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| schemaVersion                                                      | Explicit dispatch to literal 2.2.0 only                                    |
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

Absent/invalid attribute containers both yield Recording.attributes=(), as required
by the existing canonical model; source presence plus targeted warnings distinguishes
them from a valid empty array. Valid siblings retain order after defective entries.
GPS ABSENT/PRESENT/INVALID and per-slot `fix=None` remain explicit. An acceleration-only
Apple Watch success is complete for available data, not proof of M3 analysis readiness.

Owner defaults never enter the source tree. Negative GPS speed/course/accuracy and
suspicious finite readings remain raw evidence with warnings, not verified speeds,
units or sentinels. Float rounding/underflow does not replace exact source tokens.
Coordinates, timestamps, epochs, force units, axes and end-index convention remain open.

## Shared diagnostic budget and ordering

One per-call collector spans motion and optional validation, including warning/info
and error records. It checks `limits.max_diagnostics` while generating diagnostics;
it does not allocate an unbounded list and truncate it afterward. Standalone motion
and optional parsers use the same guard with independent per-call budgets.

Exactly the limit is accepted if no further diagnostic is needed, including when
motion fills the budget and optional parsing is clean. The next record replaces
the last slot with a fatal RESOURCE_LIMIT_EXCEEDED at the triggering pointer/index;
validation stops and no Recording is returned. Core errors may sort before that
resource error: the unchanged order is severity, escaped JSON Pointer, then code,
with stable emission order for exact ties. No successful warning set is silently truncated.
Decoder failures remain fail-fast single-diagnostic results and fit every positive budget.

All byte/depth/sequence/node/object/string/number budgets apply to unknown content
as well as interpreted fields before domain allocation. Defaults and permitted
configuration follow the import decision; limits are not peak-RAM or throughput guarantees.
Messages identify defects without source values, GPS traces or exception payloads.
Warning definitions are in the motion/optional guides; whole-document errors in the decoder guide.

## Later versions

To add a schema version, obtain authorized source evidence, inventory it and record
differences in the schema inventory and source-contract ADR. Add explicit decoder dispatch and matching
version-specific motion/optional adapters before full service composition, plus
positive/negative byte/Path/integrity tests. Preserve 2.2.0 regressions and reject
unknown versions until their contracts are implemented. Merely adding a version to
the decoder map does not establish correct full-import semantics for another schema.

## Regression and measurement

```powershell
uv run pytest tests/test_import_service.py tests/test_motion_parser.py tests/test_optional_parser.py tests/test_project.py
uv run python tests/benchmark_importer.py --repetitions 5
```

Tests exercise both public adapters, all five complete originals, byte equality,
all available arrays/metadata, repeated/concurrent parsing, unknown nested fields,
decoder and aggregate diagnostic limits, optional recovery, core failures and
fresh-process Qt/network/write guards. Temporary test files live only in `.tmp/`.

The development-only benchmark requires native Windows, pins fixture hashes and
checks bytes/modification times before/after. It reports five untraced timed calls
after a warmup, then one separate traced allocation measurement for each adapter.
GC runs outside timings. Path timings include local reads with warm filesystem cache;
bytes input is preloaded. Tracemalloc reports Python allocations only, excluding
preexisting bytes, native allocations and total process/OS RAM. No performance
threshold is enforced. The [import boundary](../architecture/08_concepts.md#source-ownership-and-validation)
summarizes guarantees and limits. The explorer integrates this service in a background worker.
