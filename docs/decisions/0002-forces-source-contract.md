# ADR 0002 — Source ownership and import boundaries

Status: Accepted and implemented.
[DEV-REQ-002](../requirements/DEV-REQ-002-forces-importer.md) defines requirements;
[M2 acceptance](../validation/M2.md) records verification.

## Context and rationale

The [recursive inventory](../../tests/fixtures/schema-inventory.json) covers five
authorized originals, all schema 2.2.0: four iPhone exports and one Apple Watch
export. Observed structure is evidence, not a manufacturer specification.
Iron Gwazi has acceleration but no gravity/GPS; unconditional paired-sensor
requirements would reject a genuine recording. Device labels therefore describe
expected availability, not physical units, axes or calibration validity.

## Ownership and models

Own immutable original bytes, never only a mutable path. Hash retained bytes and
expose them unchanged; round-trip means identical bytes, not JSON re-encoding.
A source path is optional provenance. Use frozen/slotted dataclasses, owned
recursive mappings and tuple sequences. SourceNumber retains token plus exact
Decimal value, distinct from numeric strings and booleans.
Unknown fields, null/absence, order, GPS and precision survive.

Frozen containers alone do not own nested mutable input; copying before exposing
read-only views is deliberate. The decoder creates tree and bytes from the same
input; manually constructed envelopes cannot independently prove correspondence.
Models enforce structure without device inference or parsing.
See [model contracts](../development/CANONICAL_MODELS.md).

## Public composition and outcomes

Qt-independent `import_forces(Path)` and `import_forces_bytes(bytes)` compose
strict decoding, motion validation and optional validation in that order.
Subset success never masquerades as complete Recording success.
No network, source writes or global decoder-setting mutation occurs.

ImportSuccess owns complete available data and no error diagnostics.
ImportFailure has no recording and at least one error. Expected input/I/O defects
return structured failures; caller misuse raises TypeError/ValueError.
Unreadable, oversized or partial input never receives invented complete-source
counts/hashes. Bounded decode failures may retain bytes; schema failures may
retain the valid tree. See the [service](../development/IMPORT_SERVICE.md).

## Decoding and resource policy

Only literal schema 2.2.0 is dispatched. Require a JSON object and strict UTF-8,
retaining one accepted leading BOM. Reject duplicate decoded keys, invalid
grammar/non-JSON constants and unsupported versions. Unknown fields in the
supported version remain preserved and budgeted.

Iterative lexical preflight checks depth, nodes, objects, arrays and token lengths
before allocation; strict JSON hooks provide a second boundary. Exact Decimal
source numbers may exceed float range; typed float accessors separately require
finiteness. Do not mutate Python recursion/integer-conversion limits.

Per-call limits are positive non-boolean integers below sys.maxsize; depth is
capped at 128. [ImportLimits](../../src/ride_forces_analyzer/importers/limits.py)
and the [decoder guide](../development/STRICT_DECODING.md) own defaults/ceilings.
Accept exact thresholds, fail on overflow. Shape limits are not RAM/CPU guarantees.

Path reads reject Windows UNC/device paths and files that are not regular, check file type
before/after opening, join short reads and cap chunks at 65,536 bytes and total
reads at max_bytes+1. No oversized/partial source is presented as complete.
Mapped-drive locality, hostile ACLs/races and OS-managed access times remain outside
the verified guarantees.

## Motion, defaults and markers

Acceleration must be nonempty with complete finite x/y/z. Finite ASCII decimal
strings allow signs, fractions/exponents and leading zeros, but no whitespace,
underscores, hexadecimal, boolean or null. Original tokens survive float
rounding/underflow. Supplied gravity must be nonempty, valid and exactly paired;
never drop, pad, truncate or fabricate it. Apple Watch absence is normal;
missing iPhone gravity warns and unknown devices warn without inventing capability.

Owner defaults apply only to absent sampleRate (50) and ridingPosition (Seated),
with source/default provenance. Invalid present rate is fatal; defective posture
warns and becomes unavailable. Valid posture text with non-whitespace characters is not trimmed or
limited to a known vocabulary. Defaults do not create source fields or establish
manufacturer conventions.

Markers are mathematically integral JSON numbers, independently bounded.
Absent start/end independently use 0/N-1 with INDEX_DEFAULTED warnings and
retained source absence. Invalid supplied/reversed bounds fail; no slicing or
end-index inclusion rule is inferred. Calibration markers may precede start:
Taron gravityIndex 1513 before startIndex 2284 is valid. A gravity marker does not
create a gravity sequence. See [motion contracts](../development/MOTION_PARSING.md).

## Optional data and GPS

Retain metadata/weather, source extrema/date/smoothing tokens and arbitrary ordered
attributes without scientific interpretation. Invalid attribute entries warn at
their source index; valid typed siblings retain order. Complete Recording exposes
an empty attributes tuple for absent/invalid containers; source presence and
diagnostics preserve those distinctions.

GPS is independent of acceleration length/time. Missing iPhone GPS is informational;
Apple Watch absence is normal. Invalid containers warn and become unavailable.
Every array slot survives, including unavailable fixes. Coordinates require finite
JSON numbers; defective coordinates exclude only that fix. Other defective members
become unavailable while valid coordinates remain usable.

Negative speed/course/accuracy remain source values with warnings. Suspicious
coordinate bounds are nonfatal heuristics, not verified units. Non-increasing
timestamps compare exact values against the previous usable timed fix across gaps;
no sorting, epoch conversion or alignment occurs. Present empty/all-invalid arrays
remain PRESENT. Syntax/resource errors anywhere remain fatal.
See [optional-data contracts](../development/OPTIONAL_PARSING.md).

## Diagnostics and consequences

One independent per-call budget spans motion/optional validation; standalone
subsets allocate their own budget. Accept exactly at the limit; the next emitted
diagnostic replaces the last slot with a fatal resource record and stops.
Decoder failures use one deterministic diagnostic.

Codes, severity, RFC 6901 pointers and optional source indices are stable API data.
Sort error/warning/info, escaped pointer lexicographically, then code, preserving
exact ties. Messages identify fields/defects without source payloads or coordinates.

The boundary supports lossless inspection without asserting sensor meaning.
New schemas need authorized evidence, explicit adapters and retained regression
coverage. Source epochs, physical units/frames, end-index semantics and GPS
sentinels remain unqualified; product display evidence is scoped separately.

## References

- [Python JSON](https://docs.python.org/3.14/library/json.html): strict hooks and resource concerns.
- [Dataclasses](https://docs.python.org/3.14/library/dataclasses.html)
  and [mapping proxies](https://docs.python.org/3.14/library/types.html#types.MappingProxyType):
  ownership and immutable representations.
- [Format observations](../requirements/FORMAT-ANALYSIS.md)
  and [recording authorization](../development/RECORDINGS.md).
