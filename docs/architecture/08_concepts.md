# 8. Cross-cutting Concepts

<!-- cspell:words NFKC -->

[Architecture index](README.md)

## Source ownership and validation

`SourceEnvelope` owns original bytes, exact number tokens, an immutable source tree
and provenance. Typed values supplement that evidence; unknown fields, ordering,
GPS slots and null/absence distinctions remain intact. Defaults never alter source data.

Path imports and explicitly compressed byte imports expand bounded Raw-DEFLATE
`.zforces` before JSON validation.
Provenance identifies the original compressed file, while the tree represents
decoded JSON. Both file formats use the same downstream contracts.

The importer dispatches schema 2.2.0 and the recognized unversioned RFDB profile.
Absent rate/riding position use 50/Seated with explicit default provenance;
absent start/end independently use 0/N−1. Invalid supplied core fields fail.
Gravity and GPS are never fabricated. Optional recovery requires usable motion;
global resource failures remain fatal.

Diagnostics retain stable codes, escaped JSON Pointers and original indices,
ordered by severity/pointer/code with stable ties. Complete-service success owns
a full recording; caller misuse raises. [Import contracts](../development/IMPORT_SERVICE.md)
own budgets and adapters; the [catalog](../development/RECORDINGS.md) owns
fixture identities, observed schemas and recording authorization.

## Scientific provenance and gates

Each analysis product retains source identity, configuration, units/frame,
capability and calculation provenance. Immutable buffers and validity masks
distinguish missing data from zero. VERIFIED, PROVISIONAL, UNAVAILABLE and INVALID
apply per channel; structural correctness does not certify rider loading.

Two calculation paths have distinct contracts:

- The adopted display path normalizes admitted rounded source directions, projects
  acceleration and applies a centered 1–51-sample odd mean, default 11. Recording
  edges shorten and renormalize. Source hashes identify evidence, not eligibility.
  RFDB calibration Y/X/Z supplies provisional vertical/lateral/longitudinal axes.
- Explicit device/frame APIs require source-bound unit/quantity declarations and
  a proper orthonormal basis for passive transforms. Caller declarations do not
  qualify physical mounting, units or yaw. Gravity is not combined with acceleration.

Positive lateral means right and positive longitudinal means acceleration in the
display path. Independent tilt compares source gravity with effective vertical.
User Gravity/Incline references are provisional and do not establish safety limits.
[Decisions](09_architecture_decisions.md), [analysis APIs](../development/ANALYSIS_MODELS.md)
and [source comparisons](../validation/APP_REFERENCE.md) retain exact scientific rules.

Prepared airtime context labels and optional detected episodes are separate.
Events require explicit configuration, preserve gaps and incomplete boundaries,
and remain provisional. [Context](../implementation/AIRTIME.md) and
[event rules](../implementation/AIRTIME_EVENTS.md) own their thresholds.

## Snapshot lifetime and reuse

A `RecordingAnalysis` binds the complete import to immutable stages. Reuse requires
matching configuration and identical actual input dependencies. A smoothing change
retains projection, source/time and independent orientation; dependent consumers
rebuild. Context/events bound to projection survive smoothing changes.

Custom reference calibration is upstream: Gravity changes rebuild basis, forces,
dependent context/events and tilt; Incline changes retain tilt. Ride-bound changes
retain numerical stages. Resetting references restores the exact rounded source
directions. The [calibration API](../development/ANALYSIS_MODELS.md#reference-calibration)
defines the fixed reference window and dependency checks.

The service retains current state, active calculations and queued deliveries,
not predecessor snapshots or configuration history. Views release replaced data;
running exports retain their bound snapshot until completion. Normal reference
lifetime releases buffers when no consumer needs them.

Stage availability, row validity, scientific capability and service request state
are separate. Unavailable stages have reasons and no fabricated payload.
Evaluated events may be empty; not-evaluated events have a reason and no collection.
A failed request retains the last complete snapshot with its own revision/configuration.
[Runtime](06_runtime_view.md#explorer-analysis-delivery) owns delivery guards.

## Explorer state and time

Presentation formats prepared values; widgets own cursor, selection, viewport and
visibility. Changing those values does not recalculate analysis. Failed imports
retain the previous view.

Recording seconds are `index / effective_rate`, not an acquisition epoch.
Integer-rate replay uses start-relative `MM:SS.ff`, with a sample counter;
fractional rates use seconds. Effective user start defines replay zero while
original markers/time retain source provenance. Gravity/GPS retain independent
indices and clocks; they are not silently aligned with force samples.

Marker overrides are stored by source hash. New imports/jobs restore valid choices;
queued jobs retain their captured recipe regardless of later preferences.
Reusable presets contain no file-specific overrides.

Playback maps monotonic elapsed time to existing samples at 0.5×, 1× or 2×.
Seeking/speed changes preserve the appropriate clock origin; end stops playback.
Continuous position moves the cursor, while displayed values remain sampled.
Selections are inclusive. Inspector extrema follow the visible interval,
independently of From/To, cursor and hidden curves.
[Explorer contracts](../implementation/RAW_EXPLORER.md) own exact navigation rules.

GPS is independent approximate spatial context. Route gaps preserve missing fixes
and time discontinuities. Optional map requests use consistent Web Mercator
route/tile projection; unsupported polar coordinates retain the local route view.
Requests reveal the viewed area and IP address, not the recording or full track.
The bounded SQLite tile cache retains HTTP validators/expiry; cache failure never
blocks route display. [GPS contracts](../implementation/RAW_EXPLORER.md#gps-overview)
own limits and network behavior.

## Appearance and localization

UI themes share semantic force/context colors and preserve analysis/view state.
System appearance follows Qt's effective OS scheme; unknown schemes fall back to
dark. Settings preview themes and restore the previous choice on cancellation.
Native OS file pickers retain platform-controlled appearance.

The typed language registry supplies English, German and French catalogs, locales
and number separators. Formatting changes displayed numbers, not source tokens,
identifiers, opaque values or replay counters. Diagnostics retain original codes
and messages alongside localized explanations. Export settings bind their own
language, independently of later UI changes.
[Localization](../development/LOCALIZATION.md) and [appearance](../user/APPEARANCE.md)
own catalog and theme details.

## Rendering and persistence

Layouts own named positions and geometry; previews, composition and encoder
padding share centrally resolved geometry. Full frame retains native HD for HUD
and 4K for other layouts. Content-area frame generation/encoding retain the complete
native layout image, including empty pixels, without cropping, scaling or added padding;
HUD admits Full frame only. Preview backgrounds are presentation-only; complete
resolved frames are fitted without changing their aspect ratio. Gallery entries
use Full frame when a plugin cannot provide the requested extent.
The assistant selects export areas through plugin capabilities, hides placement
for Content area and Full-screen-only positions, and displays resolved output
dimensions and extent-specific estimates. Retained placement returns with Full frame.
Previews use the exact cursor, while video frames follow an independent
deterministic clock. The 23.976 and 59.94 options retain exact `24000/1001` and
`60000/1001` timing.
Transparent ProRes and opaque H.264 are separate outputs, published only after
successful encoding. Existing videos require explicit replacement confirmation;
failure or cancellation preserves them. Video alignment remains external.

SQLite separates application preferences, versioned export definitions, map
tiles and the Library schema. Preferences retain language/appearance, folders, restore/update consent,
render-job count and source-bound marker choices. Invalid/unavailable values use
documented defaults without destroying stored data. Presets/jobs retain complete
recipes, not recordings or prepared arrays. Omitted optional stored fields use
declared model defaults, while required fields and supplied values remain strictly
validated. Reads do not rewrite stored definitions. Batches reimport/check hashes and run
sequentially, preserving completed videos across later failure/cancellation.

The separate `library.sqlite3` contains recordings, export history and video links,
plus Alembic's revision table. Explicit import stores only complete successful
originals, initializing current markers from source/defaults and valid preferences.
Source UUIDs identify recordings across compressed/plain and changed exports.
Equivalent source objects preserve the existing entry; changed exports replace
source fields, retaining first import time, additions, valid markers and relationships.
Invalid/missing UUIDs fall back to exact-byte identity. The UUID migration merges
existing duplicates into the earliest entry and retains all export/link relationships.
Reopening verifies lengths/digests and uses the stored
compressed/plain format through the existing importer and analysis services.
The grouped list reads metadata and export counts without fetching source BLOBs.
Park keys and combined name text use NFKC normalization and case folding, populated
on import/update and backfilled for existing rows by the search migration. Park
selection and literal search terms combine with AND in parameterized metadata
queries. Park choices include all effective names regardless of the current search.
Selecting one entry reopens only its stored original, using generation-guarded worker
delivery; a failed open retains the previous chart. Read-only details preserve
original source/date/import values. Filtering preserves the loaded chart; hiding the
panel retains the filters. Current metadata additions occupy existing override/notes
columns. The update boundary rejects original/date fields and atomically refreshes
effective-name projections. A separate dialog supports Save, Cancel and reset;
no metadata history is stored. Original metadata remains immutable alongside
`ImportSuccess.additions`; effective metadata preserves explicit user provenance.
New export snapshots capture effective metadata as version 2; version-1 snapshots
and legacy batch jobs without additions retain original-source semantics. Captured
batch additions remain independent of later Library edits.
Workflow status remains one current scalar. The update boundary admits all six
fixed states in any order and touches no source, markers, metadata or relationships.
No export/import/metadata action automatically advances or resets it. The Library
foreground selector saves a clicked state immediately; failure preserves the old
value and icon, with a visible explanation. No history or new schema is introduced.
`LibraryStore` applies bundled major/minor revisions in an
explicit SQLite transaction, rolling back schema, data and revision together on
failure. Unknown revisions or unversioned existing tables are rejected without
replacement; current revisions are not rewritten. Every ordinary `sqlite3`
connection enables foreign keys and commits or rolls back its transaction.
Source formats/statuses, byte lengths and nonnegative values have SQL constraints;
archive import validates source decoding and byte identity; complete snapshot
relationships belong to the later export-history service. Existing databases are not migrated or consolidated.

Update lookup stays outside widgets. It requires a matching platform asset;
download/installation remain manual. [Deployment](07_deployment_view.md#local-export-configuration),
[video contracts](../implementation/VIDEO_EXPORT.md), [batch contracts](../implementation/EXPORT_BATCHES.md)
and [release discovery](../development/RELEASE.md#in-application-update-discovery)
own storage paths and detailed policies.
