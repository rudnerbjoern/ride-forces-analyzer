# Library storage and service contracts

<!-- cspell:words NFKC -->

The Library archives individual recordings, current additions/markers, manual
workflow, video links and export recipes. Two recordings of one ride remain two
entries. Names: **Library** (English), **Bibliothek** (German), **Bibliothèque** (French).

- [Architecture](../architecture/05_building_block_view.md#importer-composition-and-interfaces): components;
  [runtime](../architecture/06_runtime_view.md#library-actions-and-shared-windows): delivery and shared windows.
- [Data model](../architecture/08_concepts.md#library-data-model): relationships;
  [deployment](../architecture/07_deployment_view.md#local-export-configuration): database locations.
- [Explorer interactions](../implementation/RAW_EXPLORER.md#library-interactions): panels and dialogs;
  [import projection](IMPORT_SERVICE.md#library-metadata-projection): source names and date evidence.

`LibraryStore` owns `library.sqlite3`: three Library tables and Alembic's version
table. Queries use `sqlite3`; Alembic/SQLAlchemy serve migrations only. Preferences,
presets, batches and map tiles retain separate stores. No ORM, database server,
park/ride master catalog, sample table or search service is involved.
Original inputs are read-only; rendered media remain external.

## Archive import and source identity

- `LibraryArchive.import_paths()` imports each `.forces`/`.zforces` input independently.
  Main Import, drops, command-line/desktop requests and restored paths archive all
  selected inputs and open only the first successful result from stored bytes.
  **Import in new window…** opens that result in one additional window.
- `LibraryStore.archive()` stores complete original bytes, basename, format, length,
  SHA-256 and first successful UTC import time in one transaction. It initializes
  `imported` workflow and source/default markers, admitting valid saved preferences.
  Failed inputs create no partial row and do not stop the remaining inputs.
- A normalized nonzero source UUID identifies one recording across paths and formats.
  Missing/invalid UUIDs use exact-byte identity; names/dates never merge recordings.
  Equivalent decoded source objects retain the first bytes and entry unchanged.
- A changed export of the same UUID replaces source bytes/hash/filename/metadata and
  reassigns foreign keys atomically, preserving first import time, additions,
  workflow, links, history and valid markers. Incompatible markers reject the update.
  The explicitly imported source wins; no version history or older-export detection
  is maintained. Name-search projections update in the same transaction.
- `LibraryArchive.reopen()` verifies byte count/SHA-256 and prepares analysis through
  the existing importer using current Library markers. `.zforces` uses explicit
  `compressed=True` and bounded Raw-DEFLATE decoding. No temporary source file,
  JSON reconstruction or external original is needed; failure preserves the chart.

## Metadata additions and export compatibility

`RecordingAdditions` holds optional ride/park, Row/Seat/Train text labels,
Seated/Flying posture and notes separately from immutable original metadata.
Numeric/string source attributes retain their types. Unset overrides inherit source
values/provenance, including unfamiliar source postures; reset removes additions.
Recording/import dates, source fields and derived day/time zone are not editable.

`LibraryStore.update_metadata()` validates these fields and atomically replaces
additions and effective-name projections. `ImportSuccess.additions` exposes frozen
effective metadata/attributes to lists, reopened recordings and exports. Posture
overrides carry `user` provenance and change display ranges, not force calculations.
Only current additions are stored, without an edit history.
Opening the metadata editor reads current saved additions, including when the
recording is already open and window reuse avoids reloading its source or analysis.

| Saved representation          | Metadata contract                                                           |
| ----------------------------- | --------------------------------------------------------------------------- |
| `ExportSnapshot` version 2    | Captures effective ride/park/row/seat/train, posture/provenance and notes   |
| `ExportSnapshot` version 1    | Uses original-source metadata                                               |
| Batch job with additions      | Uses its captured additions independently of current Library edits          |
| Batch job without additions   | Uses original-source metadata                                               |
| JSON data export              | Uses effective metadata while retaining source dates/unknown attributes     |

## Current recording markers

The Library is authoritative for archived Start/End bounds and Gravity/Incline
references, calibration algorithm version and reference window. Preferences supply
valid initial choices on first archive and remain authoritative for non-archived
inputs; the databases are separate. Reopening/reimport restores Library choices.
Storage failures never fall back to stale preferences.

Start/End are ordered inclusive indices. Gravity/Incline are independent source
indices and may lie outside those bounds. Unset references retain the source basis;
unavailable calibration is not fabricated. Reset restores source/default bounds and
calibration without inventing originally absent marker lines.
`LibraryStore.markers()` reads the recipe without source BLOBs; `update_markers()`
validates and replaces all choices atomically. Source bytes/dates, additions,
workflow and captured export/job recipes remain unchanged. The
[analysis delivery contract](../implementation/RAW_EXPLORER.md#time-zoom-and-selection)
defines adoption and failed-save handling.

## Manual workflow states

1. **Imported** (`imported`): archived and waiting for review.
2. **Markers verified** (`markers_verified`): Start, End, Gravity and Incline have
   been reviewed and adjusted where applicable; unchanged choices can also be
   confirmed as reviewed.
3. **Overlays created** (`overlays_created`): all overlay exports needed for the
   intended video work are ready, whether one or several.
4. **Video ready** (`video_ready`): POV and overlays have been combined in external
   video software and the finished video has been exported.
5. **Uploaded** (`uploaded`): uploaded to YouTube or another platform, possibly
   private, unlisted or scheduled for later publication.
6. **Completed** (`completed`): the intended videos have been released/published
   and the user considers the work finished.

First import sets `imported`. `LibraryStore.set_workflow_status()` accepts any
of the six states without transition prerequisites, updates only the current scalar
and leaves it unchanged on failure. Edits, imports, exports and video links never
advance/reset it. External editing and publication are user-confirmed; no workflow
history or platform integration is maintained.

## Video links and label preferences

Links belong to a recording, independently of overlay attempts. Multiple full-video,
Short/TikTok or other variants can coexist. `LibraryStore` validates HTTP/HTTPS URLs
offline and scopes edits/removal to recording digest plus link ID. Only current
links are retained; sources, metadata, workflow and other links remain unchanged.
Private/unlisted/scheduled URLs need no online verification and imply no completion.
List metadata includes `video_link_count`, obtained with the existing relationship
index without reading source bytes or fetching links separately per recording.
The same offline URL validator admits both saved links and explicit browser opening.

Ordered options live as JSON in `Preferences.library_video_labels`, without a label
table. Defaults are YouTube, Shorts, TikTok, Reel, Facebook and Instagram only when
no saved list exists. Customized and explicitly empty lists persist. Labels must
be nonempty and distinct; an unset link label is empty text. Each link retains its
label when options are renamed/removed. The dropdown retains saved unavailable
labels; new choices are managed in Settings rather than a free-text link editor.
`LibraryLabelsEditor` holds a draft: Save writes the ordered list; Cancel writes
nothing. [Explorer interactions](../implementation/RAW_EXPLORER.md#library-interactions)
define per-link Save/Remove and unsaved-form handling.

## Export history and repeat export

`LibraryHistory` stores one row per started single-video, data or batch attempt,
linked by source SHA-256. Retries remain distinct; skipped jobs create no row.
`ExportRequest` version 1 freezes requested format, range, analysis configuration,
metadata and video settings before preparation. Effective video recipes use the
shared `ExportSnapshot`; data recipes use the validated request representation.

| Attempt        | Start / duration contract                                                  |
| -------------- | -------------------------------------------------------------------------- |
| Single video   | Start initiates preparation; destination-picker cancellation is recorded   |
| Data           | Worker starts after destination/overwrite confirmation                     |
| Batch job      | Starts before source loading; skipped jobs never enter the lifecycle       |

`ExportAttempt` wraps preparation/execution and records actual completion, failure
or cancellation. Monotonic duration includes preparation/execution, excluding
destination-picker and queue waiting. Completion follows successful publication;
output path/size and GPU selection remain unknown until actually observed.
History-write errors are separate from exporter outcomes and never remove successful
files; batch reports expose `history_error`. Startup changes leftover running rows
to interrupted with unknown finish time/duration. Workflow status stays manual.

`prepare_repeat()` verifies archived bytes and reconstructs captured metadata and
analysis without current Library/preference/preset values or source/output paths.
Recomputed video geometry/timing must match the captured snapshot.
Supported video recipes open the assistant review; data recipes retain format/range
and use destination/overwrite confirmation. Each started repeat creates a new row.
Unsupported snapshot/algorithm versions or source-identity mismatch explain why a
repeat is unavailable, without changing saved history or substituting defaults.
Changing current presets, markers or additions cannot rewrite captured recipes;
matching settings do not promise identical encoder bytes across versions/hardware.
History is accessible independently of batch run reports.

## Database tables and query contracts

`recordings` has one-to-many relationships with `export_history` and `video_links`.
Source digests identify the stored bytes; normalized source UUIDs identify one
recording across exports. Export attempts and links use local integer keys.
All stored timestamps are UTC ISO 8601 text with six fractional digits and `Z`;
`recorded_day` is `YYYY-MM-DD`. Nullable values use SQL `NULL`. Import time is
captured on first successful insertion, separately from recording time.
The [data model](../architecture/08_concepts.md#library-data-model) shows relationships
to the independent preference, export and map-cache stores.

### Table: `recordings`

| Field                           | SQLite type / constraint            | Purpose                                                                         |
| ------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------- |
| `source_sha256`                 | `TEXT PRIMARY KEY NOT NULL`         | Current source digest; relationships follow source replacements.                |
| `source_uuid`                   | `TEXT NULL UNIQUE`                  | Canonical source UUID identifying one recording across exports.                 |
| `source_bytes`                  | `BLOB NOT NULL`                     | Exact original `.forces` or compressed `.zforces` bytes.                        |
| `source_filename`               | `TEXT NOT NULL`                     | Original basename; opening the archive does not depend on its old path.         |
| `source_format`                 | `TEXT NOT NULL`                     | `forces` or `zforces`, used to select the decoding path.                        |
| `source_byte_count`             | `INTEGER NOT NULL`                  | Expected original length for integrity checks.                                  |
| `source_ride_name`              | `TEXT NULL`                         | Verbatim source ride name.                                                      |
| `source_park_name`              | `TEXT NULL`                         | Verbatim source park name.                                                      |
| `recorded_at_utc`               | `TEXT NULL`                         | Derived recording instant, only with a verified interpretation.                 |
| `recorded_day`                  | `TEXT NULL`                         | Day used for grouping, derived from the instant and day time zone.              |
| `day_timezone`                  | `TEXT NULL`                         | Valid source time zone, explicit UTC fallback, or unknown.                      |
| `imported_at_utc`               | `TEXT NOT NULL`                     | First successful Library import time.                                           |
| `first_sample`                  | `INTEGER NOT NULL`                  | Current inclusive Start marker resolved through the existing contract.          |
| `last_sample`                   | `INTEGER NOT NULL`                  | Current inclusive End marker, at or after Start and within the recording.       |
| `gravity_index`                 | `INTEGER NULL`                      | Custom Gravity reference; `NULL` retains the original source basis.             |
| `incline_index`                 | `INTEGER NULL`                      | Custom Incline reference; `NULL` retains the original source basis.             |
| `calibration_algorithm_version` | `TEXT NOT NULL`                     | Version of the existing calibration-reference recipe.                           |
| `calibration_window_samples`    | `INTEGER NOT NULL`                  | Reference window required by the existing calibration recipe.                   |
| `ride_name_override`            | `TEXT NULL`                         | Editable replacement; `NULL` uses the source name.                              |
| `park_name_override`            | `TEXT NULL`                         | Editable replacement; `NULL` uses the source park.                              |
| `row_override`                  | `TEXT NULL`                         | Editable Row label; `NULL` uses the source attribute.                           |
| `seat_override`                 | `TEXT NULL`                         | Editable Seat label; `NULL` uses the source attribute.                          |
| `train_override`                | `TEXT NULL`                         | Editable Train label; `NULL` uses the source attribute.                         |
| `riding_position_override`      | `TEXT NULL`                         | Editable `Seated`/`Flying` value; `NULL` retains the imported value/provenance. |
| `notes`                         | `TEXT NOT NULL`                     | Editable free text, initially empty.                                            |
| `workflow_status`               | `TEXT NOT NULL`, default `imported` | Current manual workflow state; one of the six values defined above.             |
| `park_key`                      | `TEXT NULL`                         | Normalized effective park name for filtering.                                   |
| `search_text`                   | `TEXT NOT NULL`                     | Normalized effective ride and park names for search.                            |

Source bytes, identity, original metadata, recording date/day/time zone and first
import time are not editable in Library editors. An explicit changed-source reimport
updates source fields while preserving the first import time. Effective metadata uses overrides when set, otherwise
source values. The user cannot change the date through the Library editor or its
update service. `park_key` and
`search_text` are disposable query projections, updated in the same transaction as
name edits; they are not additional source data. List queries select metadata only,
not every recording BLOB or parsed measurement array.

### Table: `export_history`

| Field                  | SQLite type / constraint | Purpose                                                                          |
| ---------------------- | ------------------------ | -------------------------------------------------------------------------------- |
| `id`                   | `INTEGER PRIMARY KEY`    | Local export-attempt identifier.                                                 |
| `recording_sha256`     | `TEXT NOT NULL`, FK      | References `recordings.source_sha256`.                                           |
| `export_kind`          | `TEXT NOT NULL`          | Video, CSV, app-shaped JSON or Analyzer JSON, using existing format identifiers. |
| `origin`               | `TEXT NOT NULL`          | Single export or batch job.                                                      |
| `started_at_utc`       | `TEXT NOT NULL`          | Attempt start, including preparation.                                            |
| `finished_at_utc`      | `TEXT NULL`              | Completion, failure or cancellation time when known.                             |
| `duration_seconds`     | `REAL NULL`              | Measured attempt duration; excludes queue waiting.                               |
| `status`               | `TEXT NOT NULL`          | Running, completed, failed, cancelled or interrupted.                            |
| `application_version`  | `TEXT NOT NULL`          | Application that created the attempt.                                            |
| `request_json`         | `TEXT NOT NULL`          | Versioned frozen requested settings; available even if preparation fails.        |
| `export_snapshot_json` | `TEXT NULL`              | Versioned effective settings/recipe; required for completed, repeatable exports. |
| `output_path`          | `TEXT NULL`              | Historical destination; video/data bytes remain external.                        |
| `file_size_bytes`      | `INTEGER NULL`           | Completed output size.                                                           |
| `gpu_encoding`         | `INTEGER NULL`           | Observed GPU use, where applicable; unknown before encoder selection.            |
| `error`                | `TEXT NULL`              | Failure/cancellation explanation, if available.                                  |

### Table: `video_links`

| Field              | SQLite type / constraint | Purpose                                                                             |
| ------------------ | ------------------------ | ----------------------------------------------------------------------------------- |
| `id`               | `INTEGER PRIMARY KEY`    | Local link identifier.                                                              |
| `recording_sha256` | `TEXT NOT NULL`, FK      | References `recordings.source_sha256`; several links may belong to one recording.   |
| `url`              | `TEXT NOT NULL`          | User-supplied video URL.                                                            |
| `label`            | `TEXT NOT NULL`          | Selected Library dropdown value; empty if unset, retained if its option is removed. |

Use foreign keys on every connection and validate the admitted formats/statuses,
nonnegative sizes/durations and snapshot/source relationships in the storage/service
boundary. Keep existing Pydantic snapshot validation. There is no presets, batch-run
or per-frame duplication in this database. Removing a Library entry deletes its
archived bytes, additions, markers, video links and export history in one transaction.
A running export for that recording blocks removal; a failure preserves all data.
External original/output files are never removed. Deleting an external original
or output file never deletes Library history.

### Indexes and query behavior

| Index                          | Fields / order                                                                           | Use                                                    |
| ------------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Primary key                    | `recordings(source_sha256)`                                                              | Exact duplicate lookup and source joins.               |
| `idx_recordings_uuid`          | `source_uuid` (unique)                                                                   | Recording identity across formats and changed exports. |
| `idx_recordings_day`           | `recorded_day DESC, recorded_at_utc DESC, imported_at_utc DESC, source_sha256`           | Day groups and stable newest-first entries.            |
| `idx_recordings_park_day`      | `park_key, recorded_day DESC, recorded_at_utc DESC, imported_at_utc DESC, source_sha256` | Same ordering within a selected park.                  |
| `idx_export_history_recording` | `recording_sha256, started_at_utc DESC, id DESC`                                         | Selected recording's history, count and latest export. |
| `idx_video_links_recording`    | `recording_sha256, id`                                                                   | Lookup and ordering of video links for one recording.  |

The export integer primary key needs no duplicate index. Display-only fields have
no separate indexes. The Library uses ordinary queries and the existing Qt
model/view facilities, without persisted SQL views.

`LibraryStore.entries()` combines optional park, workflow-status and search filters
with AND, preserving the existing day/instant ordering. A status must be one of
`WORKFLOW_STATUSES`; `None` includes every state. Filtering reads metadata only
and never changes the manual status or archived data.

Search matches every whitespace-separated term against combined effective ride/park
names. Names and terms use Python NFKC normalization and `casefold`; display spelling
is preserved. Parameterized `instr` predicates provide literal substring matching,
including `%`, `_` and escape characters.
SQLite's default `LIKE` does not provide general Unicode case folding; see its
[documented behavior](https://www.sqlite.org/lang_expr.html#the_like_glob_regexp_match_and_extract_operators).
A contains search scans this small metadata set; these B-tree
indexes do not accelerate it. A dedicated full-text index, ranking and query
language are not required for the requested ride/park search.

## Schema migrations

[Alembic](https://alembic.sqlalchemy.org/en/latest/) applies a linear chain of explicit
revision scripts before Library access. `alembic_version.version_num` stores the
revision independently of app patch, export-snapshot and backup-format versions.
IDs use the introducing app major/minor (`1_3`); descriptive suffixes identify the
UUID/search revisions. Released scripts are immutable; unchanged schemas need no
empty app-version migration. Generated proposals require review.

- `1_3`: Library tables and indexes.
- `1_3_identity`: normalize/backfill UUIDs and merge duplicates into the earliest
  entry, retaining its source/choices and all links/history. Explicit reimport
  updates that retained source.
- `1_3_search`: backfill normalized effective-name projections from metadata and
  overrides without reading source BLOBs.

Scripts ship in wheels/native packages and run offline through the Python API;
no external CLI is needed. Explicit SQLite transactions roll back schema, data and
revision together. [SQLite batch operations](https://alembic.sqlalchemy.org/en/latest/batch.html)
preserve source bytes, additions, snapshots and relationships during table rebuilds.
Current schemas are not rewritten; unknown/newer revisions and unrecognized
unversioned tables are rejected without replacement. There is no automatic
downgrade or custom migration framework. Only derived projections can be rebuilt.

## Portable backup and restore

A portable ZIP contains a versioned `manifest.json`, UTF-8 `recordings.jsonl`,
`exports.jsonl`, `video_links.jsonl` and exact binary originals under
`sources/<sha256>.forces` or `.zforces`. The manifest records the source Alembic
revision separately from backup-format version and includes saved video-label
options. Metadata retains lengths/digests, first import times, additions,
markers/calibration, workflow, links, history and complete recipes. IDs may be
remapped; recording relationships use digests. Originals are never JSON-rewritten
or Base64-expanded. External media, map caches, unrelated preferences and preset/
batch stores are excluded; no additional backup dependency is needed.

Backup uses a consistent SQLite online snapshot, reads saved label options once
and publishes only complete ZIPs. Unsaved Settings drafts are excluded. Restore
validates format versions, members, lengths/hashes, decoding, indices and
relationships in a staged current-schema Library before replacement.

| Missing optional content      | Restore policy                                       |
| ----------------------------- | ---------------------------------------------------- |
| Source projections            | Recover from archived originals                      |
| Bounds/calibration/workflow   | Source indices, default recipe, `imported`           |
| Import timestamp              | Unknown, represented by empty text                   |
| Export recipe                 | Empty; cannot repeat                                 |
| Link URL/label                | Empty values for editing                             |
| Label options                 | Defaults when absent; explicitly empty stays empty   |
| Other optional fields         | SQL NULL or declared domain/schema defaults          |

Unknown fields are ignored. Essential source bytes, unambiguous identity, integrity
and valid relationships remain required; invalid supplied values are rejected.
Limits: 4 GiB compressed/expanded; 100,000 members and rows per metadata file;
256 MiB per JSON Lines file; existing source-import byte limit per original/row.
Traversal, symlinks, encryption, duplicate/unexpected members and source identities
are rejected; members are not extracted by name.

After explicit confirmation, one SQLite transaction replaces only Library tables
and the attached `library_video_labels` preference. Standard rollback journals
provide cross-database atomicity. Active running exports block replacement;
restored unfinished attempts become interrupted. Cancellation/write failures
before commit roll back both data and labels, preserving the active Library.
External paths are never restore inputs. Workers support cooperative cancellation;
completed restore applies immediately and is not undone by Settings Cancel.
The label draft refreshes; unrelated Settings drafts retain Save/Cancel behavior.
Library merging/conflict resolution, scheduled backups and embedded videos are
outside the supported format.

## Verification ownership

The maintained acceptance contracts are exercised by focused native Windows suites:

| Contract                                                                                                 | Regression ownership                                                                                 |
| -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Source names/dates, time-zone independence and original tokens                                           | `tests/importers/test_library_metadata.py`, recording integrity tests                                |
| Fresh/current/older schema, unknown revisions, constraints and rollback                                  | `tests/storage/test_library.py`                                                                      |
| UUID identity/update, independent failures, missing originals and archived-byte integrity                | `tests/explorer/test_library.py`                                                                     |
| Metadata, markers and manual workflow persistence without source changes                                 | Explorer/storage Library tests, `tests/ui/test_library_panel.py`, `tests/ui/test_ride_markers.py`    |
| Panel geometry, filtering, scrolling, context actions, confirmed removal and independent windows         | Library panel/context-menu tests, `tests/ui/test_recording_windows.py`                               |
| Label defaults/custom/empty lists and isolated link edits                                                | `tests/ui/test_library_videos.py`, preference/storage Library tests                                  |
| Actual export outcomes, frozen metadata/recipes, unsupported repeats and overwrite protection            | `tests/exports/test_library_history.py`, `tests/ui/test_library_exports.py`, rendering/batch tests   |
| Complete portable restore, tolerant optional fields, unsafe archives, cancellation and atomic rollback   | `tests/storage/test_library_backup.py`, `tests/ui/test_library_transfer.py`                          |

Group related GUI checks in shared native-window sessions. Use the existing
[Windows checks](SETUP.md#required-project-checks) and
[quality/evidence rules](CODE_QUALITY.md); scientific evidence and recording
authorization remain in their designated source-contract and recording documents.
