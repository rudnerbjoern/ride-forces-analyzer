# 8. Cross-cutting Concepts

[Architecture index](README.md)

## Source ownership and validation

SourceEnvelope owns original bytes, an immutable recursive tree and provenance.
Canonical floats supplement exact tokens; unknown fields, ordering, null/absence,
GPS slots and metadata remain retained. Defaults never alter source data.
Absent rate/riding position use 50/Seated; absent start/end independently use
0/N-1 with warnings. Invalid supplied core data fails; missing sensors stay absent.

Only schema 2.2.0 is dispatched. Strict decoding, configurable resource budgets
and one per-call diagnostic budget protect the boundary. Core failure stops
optional validation; optional recovery requires usable motion. ImportSuccess owns
a complete Recording; ImportFailure has none. Diagnostics sort by severity,
escaped JSON pointer and code with stable ties. Caller misuse raises.
[Importer contracts](../development/IMPORT_SERVICE.md) own exact API details.

The five original fixtures contain 48,029 acceleration vectors, 39,317 available
gravity vectors and 698 GPS fixes. iPhone recordings have paired gravity/GPS;
the Apple Watch fixture lacks both. Taron/Voltron omit sampleRate, so the explicit
50 Hz absence policy applies. Motion components are decimal strings; GPS fields
are JSON numbers. These corpus observations are not a manufacturer specification.
The complete machine-readable [schema inventory](../../tests/fixtures/schema-inventory.json)
and [recording catalog](../development/RECORDINGS.md) preserve reproducible source
evidence, exact hashes and publication/licensing authorization.

## Scientific provenance and gates

Analysis retains complete M2 input, source identity, algorithm/configuration,
caller-supplied UTC time, quantity/unit/frame, time basis and raw/filtered outputs.
Owned float64 buffers and validity masks distinguish missingness from zero.

VERIFIED, PROVISIONAL, UNAVAILABLE and INVALID describe individual channels.
Verified raw handling or valid result structure does not certify physical rider
loading. Device norms require explicit source-bound unit/quantity contracts;
Pint converts declared units and NumPy computes without combining acceleration
and gravity. Unknown units cannot create physical values.

The generic frame path uses proper orthonormal bases, passive
`v_target = R @ v_device`, inverse transpose, and explicit provisional permission.
Admission tolerance is absolute 1e-10, relative zero. Source directions are never
silently repaired into that basis. Gravity does not resolve yaw.
[passive frame decision](09_architecture_decisions.md#passive-frame-transforms) owns the convention;
[physical qualification boundary](09_architecture_decisions.md#physical-qualification) remains
a proposed general qualification policy.

The separate product path normalizes admitted rounded source direction rows,
projects acceleration and applies an odd centered mean, 1–51 samples (default 11).
Edges shorten and renormalize; recomputation starts from unfiltered projections.
Usable imports default to calibrated display; preparation errors retain raw data.
Source hashes establish provenance, not availability.
[source-app projection decision](09_architecture_decisions.md#source-app-projection) and
[source comparisons](../validation/APP_REFERENCE.md) define source-bound evidence.
Positive lateral means right; positive longitudinal means acceleration.
Generic RIDER-frame signs remain a separate contract.

## Explorer state and time

Qt-independent presentation prepares channels, metadata, markers, clocks,
selection validation and extrema; widgets own interactions and view state.
Failed loads retain the previous view. All metadata is plain source text.

Recording time is inferred `index / effective_rate`, not an acquisition epoch.
Integer-rate replay uses start-relative `MM:SS.ff`, with a within-second sample
counter; fractional rates use seconds. GPS never determines this clock.
Selections are inclusive; extrema use existing full channels and earliest ties,
independent of cursor, zoom and curve visibility.

Only time zooms. Recording limits bound zoom-out; one sampling interval bounds
zoom-in. Reset uses effective start/end. Force bounds pad signed extrema by 5%;
calibrated views include labeled -1/0/+1 g references.
[Explorer contracts](../implementation/RAW_EXPLORER.md) own interaction details.

GPS is independent coarse spatial reference, preserving missing fixes and gaps.
It supplies no qualified ride speed, distance, height or reconstructed track.

## Appearance and localization

Shared Qt palettes/styles cover light/dark controls, charts, GPS and native caption
integration. Theme changes preserve analysis/view state; export colors are independent.

Qt-independent `i18n` separates English templates from opaque values.
German formatting affects displayed numbers, not source tokens or replay clocks.
Weak Qt bindings update controls and dropdown geometry; the installed Qt catalog
supplies standard German dialog labels. Diagnostics keep original codes/paths and
messages alongside localized explanations. Export settings snapshot their own
language independently of the UI. See [localization](../development/LOCALIZATION.md).

## Rendering and persistence

Production RGBA frame generation is separate from FFmpeg encoding.
Shared profile/aspect geometry drives previews and video padding. Previews use the
exact cursor; encodes use an independent deterministic video clock.
Transparent ProRes and opaque H.264 are independent outputs; complete decoding
precedes exclusive publication. Manual Onride alignment remains external.

SQLite stores versioned export presets and immutable batch snapshots, not original
recordings or media. Sequential jobs reimport/check source hashes; per-job failures
continue, cancellation retains completed files and discards incomplete work.
An independent local `preferences.sqlite3` stores separate folders for the last
successful file-dialog import and video export. Missing folders or unavailable
storage fall back to native dialog defaults without blocking imports or exports.
The same preferences store retains the last selected UI language and appearance;
invalid or unavailable values fall back to the preferred OS display language
(German when German, otherwise English) and system appearance. System appearance
follows Qt's effective OS color scheme and change notifications; unknown means dark.
Explicit light/dark preferences override OS changes.
Update preferences store the optional daily startup check, last attempt time and
skipped release tag. Public release lookup and version comparison live outside
widgets; UI workers handle transport scheduling and present the result. See
[release discovery](../development/RELEASE.md#in-application-update-discovery).
See [export](../implementation/VIDEO_EXPORT.md) and
[batch](../implementation/EXPORT_BATCHES.md) contracts.
