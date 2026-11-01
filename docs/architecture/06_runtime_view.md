# 6. Runtime View

[Architecture index](README.md)

## Qt bootstrap

The module and frozen entry points initialize local error reporting before UI
imports. Settings are validated before creating recording windows.
`RecordingApplication` selects Qt dialogs before constructing `QApplication`, so
file-open, save and folder selection share the application palette and stylesheet.
`InstanceBroker` acquires local process ownership or forwards the optional file
path and `--new-window` request to the existing owner.

After instance ownership is acquired, `RecordingApplication.start()` initializes
the Library, applies pending revisions and marks leftover running export attempts
as interrupted before creating the first window. Unknown finish time/duration stays unknown.
Additional windows do not repeat startup initialization. A Library error propagates
to the existing error-reporting path and prevents creation of the initial window;
the database is not replaced or reset.

```mermaid
sequenceDiagram
    actor User
    participant Entry as Entry point
    participant Broker as InstanceBroker
    participant App as RecordingApplication
    participant Window as ExplorerWindow
    User->>Entry: Launch with optional recording path
    Entry->>Entry: Initialize support report and settings
    Entry->>Broker: Acquire ownership or forward request
    alt Existing owner
        Broker-->>Entry: Acknowledge request
        Entry-->>User: Exit launcher
    else New owner
        Entry->>App: Create application and initial window
        App->>Window: Open requested or restored recording
        App->>App: Run event loop
        User->>Window: Close last window
        App->>Broker: Release ownership after workers finish
    end
```

Locking and local sockets use the application-data namespace, bounded forwarding
and restricted local access. Failed forwarding does not start a competing owner.
macOS file-open events enter the same request queue; Linux desktop launchers pass
a file path. Requests wait while the target window imports.

Library row selection schedules the existing load worker with an archive digest
instead of an external path. It reuses archive decoding/analysis and the same
generation checks, completion and failure delivery. The list is disabled while
loading; errors remain visible in the panel and status bar without replacing the
previous chart. Additional original metadata appears only after a successful load.

Each window owns its recording, analysis, playback and child dialogs. Language
and appearance are shared. Explicit file paths take precedence over optional
Restore last file; only successful imports update the remembered path.

Support reports collect handled/unhandled errors, Qt warnings/critical/fatal
messages with severity/category and best-effort native crash stacks. Qt diagnostics
also reach the prior handler or terminal; debug/info messages are not stored.
Writes are serialized and flushed without a per-run size limit.
The first successful diagnostic write publishes report availability. Status-bar
indicators receive queued UI-thread delivery; newly opened windows read the current
state immediately. Header-only reports and failed writes do not activate the icon.
Clicking opens the report directory through the platform desktop service.
Startup removes completed-process
reports and preserves active ones. Report failure must not replace the original
error. Exception messages may contain personal paths; nothing is uploaded.

## Optional update discovery

A worker performs an opt-in startup check at most once per day or an explicit
check from Settings → Application. The Qt-independent service uses bounded HTTPS reads; the UI
discards late results after closure. Manual failures show a retry message,
automatic failures remain silent. Download and installation stay manual.
[Release discovery](../development/RELEASE.md#in-application-update-discovery)
defines selection and persistence.

## Read-only import and failures

```mermaid
sequenceDiagram
    participant Caller
    participant Service as import_forces
    participant Decoder
    participant Motion
    participant Optional
    Caller->>Service: Path or bytes, resource limits
    Service->>Decoder: Read/decompress and strictly decode
    alt Decode or schema failure
        Service-->>Caller: Structured ImportFailure
    else Supported source
        Service->>Motion: Validate core motion with shared budget
        alt Core failure
            Service-->>Caller: ImportFailure and skip optional parsing
        else Usable motion
            Service->>Optional: Validate metadata, attributes and GPS
            Service-->>Caller: Complete ImportSuccess or resource failure
        end
    end
```

Path reads are bounded and read-only; bytes imports bypass filesystem access.
Optional-data defects may retain usable core motion with warnings. Invalid supplied
gravity and global resource failures remain fatal. Caller misuse raises
`TypeError`/`ValueError`; expected input/I/O defects return structured failures.
[Import contracts](../development/IMPORT_SERVICE.md) own detailed rules.

## Explorer analysis delivery

The import worker prepares a complete immutable analysis snapshot. Expected
unavailable stages still permit raw display; failed imports retain the previous
view. The UI adopts the prepared snapshot without repeating calculations.

```mermaid
sequenceDiagram
    participant UI as Explorer
    participant Adapter as AnalysisController
    participant Worker
    participant Service as AnalysisService
    UI->>Adapter: Bind imported snapshot and subscribe
    Service-->>Adapter: Initial coherent state
    Adapter-->>UI: Apply current binding on GUI thread
    UI->>Adapter: Request smoothing or marker change
    Adapter->>Worker: Queue latest intent
    Worker->>Service: Request configuration synchronously
    Service->>Service: Advance revision and calculate outside lock
    alt Current result
        Service-->>Adapter: Complete snapshot or failure
        Adapter-->>UI: Apply only matching source, intent and revision
    else Superseded or closed
        Service->>Service: Discard completion
    end
    UI->>Adapter: Close or bind another source
    Adapter->>Service: Unsubscribe and close old service
```

The service owns revisions, current state and subscriptions, not Qt or workers.
Callbacks run outside its state lock and are serialized per subscription. Initial
state precedes subsequent notifications. Failure retains the previous complete
snapshot with its original configuration; no partial result replaces it.

The adapter checks active binding, source, revision, terminal status and UI-intent
generation again on GUI delivery. Load generations similarly reject late imports.
Thus a delayed pending message cannot undo completion, and an old error cannot
affect a new recording.

Smoothing retains projection and independent orientation. Gravity changes rebuild
calibration, forces and tilt; Incline changes retain tilt. Successful current marker
results save all choices atomically before view delivery. Stale/invalid requests do
not save; storage failure keeps session values and reports the failure.
[Snapshot concepts](08_concepts.md#snapshot-lifetime-and-reuse) own dependencies.

## Product boundaries

Cursor, selection, viewport, language and appearance are presentation state.
Visible-range extrema follow the viewport; From/To remains a separate inclusive
export interval. Playback uses monotonic elapsed time and the source sample rate;
delayed UI ticks catch up without accumulating drift. Seeking resets the origin.
Displayed values remain source samples; playback does not calculate analysis.
Video synchronization remains in external editing software.

## Implemented device-only analysis

Explicit `analysis.device` calls validate source-bound unit/quantity contracts,
convert independent sequences with Pint and calculate vectors/norms with NumPy.
Absent data/units yield unavailable channels; numerical range defects yield invalid
products without discarding independent usable channels. Caller declarations do
not certify sensor semantics. [Device API](../development/ANALYSIS_MODELS.md#device-only-vectors-and-units)
defines the contract.

## Explicit provisional frame projection

`analysis.frames` checks explicit source calibration, unit contracts, profile
permission and a proper orthonormal basis before applying passive SciPy rotation.
Available rider vectors remain provisional. No source basis repair, gravity
combination or clock alignment occurs.
[Frame API](../development/ANALYSIS_MODELS.md#passive-frame-math-and-provisional-rider-vectors)
owns admission and failure rules.

## Raw explorer interaction

Qt workers import and prepare data; Qt Charts displays raw or calibrated channels.
Calibration/preparation unavailability retains raw data with an explanation.
Navigation, zoom, curve visibility and appearance preserve the snapshot. Failed
loads preserve the previous usable view; shutdown drains background work.

The GPS dialog reads independent route data. Explicit map requests use a worker,
retain the route on failure and reject results after close/replacement. Resize
alone does not start a request. [Explorer contracts](../implementation/RAW_EXPLORER.md)
own interaction details.

## Sample data export runtime

Before destination selection, the UI pauses playback and captures the snapshot
and inclusive From/To interval. Existing destinations require explicit confirmation.
A shared worker serializes CSV or JSON and transports progress/cancellation.
Confirmed replacement commits atomically after success; failure/cancellation
preserves an existing file and removes temporary output. Only success remembers
the destination folder. The worker retains its bound snapshot until completion.
For archived hashes, worker execution starts an attempt with frozen requested
settings. Existing data validation admits its effective recipe before serialization.
Actual completion/cancellation/failure is saved independently of exporter output;
history-write errors are reported without deleting successful files.

## Video export runtime

The assistant captures its opening analysis snapshot. Preview requests select the
rounded sample at 60% of the chosen export interval, independently of the workspace
cursor. Range changes recompute it; other settings retain it. Debounced workers
receive current settings; revision checks discard outdated results.
Layout, format and extent changes invalidate the current preview and capture a
new request. Gallery and main view share images fitted to the resolved output
geometry; Full-frame-only gallery profiles retain their complete canvas.
Export binds the selected range, layout, aspect, language and analysis recipe.
Preparing the timeline captures its export-owned settings/analysis snapshot.
Single and batch encoding embed the same snapshot in the video comment; batch
reporting collects that snapshot without creating another analysis representation
or a per-video JSON sidecar.
For archived hashes, Start captures a requested recipe before timeline/encoder
preparation. It records preparation failures and destination-picker cancellation.
The worker attaches the shared effective snapshot and finalizes its actual outcome;
destination and queue waiting are excluded from monotonic attempt duration.
Successful output survives a history-write failure, which remains visible separately.

A worker streams the native Content-area image or Full-frame layout region to
FFmpeg, which retains native dimensions or pads to the chosen canvas. The local render-job
preference selects serial generation or a bounded thread pool with independent
renderers. Ordered prefetch preserves frame order. NVIDIA Vulkan/NVENC is used
only after a successful probe; CPU remains the fallback.

For single-video exports, an optional callback forwards already rendered RGBA
regions at approximately two-second video intervals, including the first and last
frame. Preview composition applies the selected display-only backdrop in the worker;
Qt signals deliver the resulting image to the dialog without a second render.

Cancellation joins active renders, cancels queued work and discards incomplete
output. Successful encoding publishes a new file exclusively or atomically replaces
an existing video after save-dialog confirmation. The user aligns the
overlay in their editor. [Video contracts](../implementation/VIDEO_EXPORT.md)
define output, timing and publication details.

## Saved batch runtime

```mermaid
sequenceDiagram
    actor User
    participant UI as Batch window
    participant Store as SQLite export store
    participant Queue as Batch service
    participant Encoder as Video export
    User->>UI: Run selected or all saved batches
    UI->>Store: Read immutable job snapshots
    UI->>Queue: Start queue in selected output directory
    Queue->>Queue: Reserve a unique run report
    loop Each job
        Queue->>Queue: Reimport, verify hash and restore saved recipe
        Queue->>Encoder: Render and encode
        Encoder-->>Queue: Completion, failure or cancellation
        Queue->>Queue: Update this run's report
        Queue-->>UI: Progress and result
    end
```

Videos run sequentially; their frames use the local render-job preference.
Before encoding, the queue reads each distinct source to calculate per-job frame
budgets from saved inclusive bounds, source sample rates and export frame rates.
Overall dialog/taskbar progress uses those frame weights; settled failed jobs consume
their planned share, while unreadable sources have no known budget.
Each job replays its saved export area through the shared geometry/encoding path,
independently of current assistant settings and later preset edits.
Per-job failures allow later jobs to continue. Cancellation skips pending jobs and
preserves completed videos. Closing the dialog requests cancellation and waits for
the active encoder. Definitions survive restart; automatic resume is outside scope.
Each started archived-source job creates its own Library attempt before import;
skipped jobs create none. The report and Library retain requested/effective settings,
observed backend and actual results; `history_error` reports independent persistence
failures. The Library history dialog prepares repeats in a worker from archived bytes
and saved recipes. Video repeats use the assistant's review; data repeats use the
existing save/overwrite flow. A started repeat creates a fresh attempt.
