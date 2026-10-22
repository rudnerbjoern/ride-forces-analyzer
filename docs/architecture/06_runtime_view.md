# 6. Runtime View

[Architecture index](README.md)

## Qt bootstrap

```mermaid
sequenceDiagram
    actor User
    participant Entry as __main__.main
    participant Settings as config.AppSettings
    participant Qt as QApplication / ExplorerWindow
    User->>Entry: Launch module with optional settings
    Entry->>Settings: Use supplied model or construct defaults
    Settings-->>Entry: Validated immutable settings
    Entry->>Qt: Construct application and raw explorer
    Entry->>Qt: Set title, dimensions and raw chart controls
    Entry->>Qt: Show window and run event loop
    User->>Qt: Close window
    Qt-->>Entry: Event loop exit code
```

AppSettings rejects unknown settings and invalid title/dimensions outside widgets.
Window dimensions are positive and at most 16,777,215 pixels, the Qt widget limit.
Invalid model construction fails before window creation. The GUI smoke test starts
the real module in a separate Windows process and exits through the Qt event loop;
its tests exercise the real bootstrap contract above.

After the event loop starts, the explorer applies the optional Restore last file
preference (off by default). Preferences supplies an existing absolute file path;
the normal background import/analysis flow loads it. A manual load already requested
or a closed window prevents the scheduled restoration. Only successful imports update
the remembered path; missing files and unavailable preference storage are skipped.

## Optional update discovery

Before normal interaction, the explorer schedules an optional update check after
the event loop starts. A controller applies the saved opt-in, daily attempt limit
and skipped version. A worker calls the Qt-independent release service; only the
GUI thread updates status or opens a release notice. Closing the main window
suppresses late results. Network operations have bounded reads/timeouts and never
block the GUI or recording processing. Manual checks in About bypass the daily
interval and show errors; automatic errors are silent. No installer is invoked.

## Read-only import and failures

```mermaid
sequenceDiagram
    participant Caller
    participant Service as Public import service
    participant Decoder as Strict decoder
    participant File as Local original
    participant Motion as Motion validation
    participant Optional as Optional validation
    participant Domain as Immutable domain models
    Caller->>Service: import_forces(Path, limits)
    Service->>Decoder: decode_forces(Path, limits)
    Decoder->>File: Bounded binary read only
    File-->>Decoder: Original bytes
    Decoder->>Decoder: Resource preflight, strict JSON and version dispatch
    Decoder-->>Service: DecodeSuccess or ImportFailure
    alt Decode / schema / I/O failure
        Service-->>Caller: ImportFailure with ordered diagnostic
    else Decoding succeeds
        Service->>Service: Create per-call diagnostic budget
        Service->>Motion: Validate motion using shared budget
        Motion-->>Service: Motion subset or ImportFailure
        alt Invalid core motion or exhausted budget
            Service-->>Caller: ImportFailure, optional validation is skipped
        else Motion succeeds
            Service->>Optional: Validate metadata, attributes and independent GPS
            Optional-->>Service: Optional data with warnings or budget failure
            alt Diagnostic budget exhausted
                Service-->>Caller: ImportFailure, no Recording
            else Complete available data
                Service->>Domain: Construct Recording with owned source
                Domain-->>Service: Immutable Recording
                Service-->>Caller: ImportSuccess with ordered warnings/info
            end
        end
    end
```

The bytes variant bypasses the file read and otherwise uses the same composition.
The public service remains synchronous; the raw explorer runs it on a Qt worker
thread with an indeterminate progress indicator. Other callers choose scheduling. Invalid caller argument types/limit configuration raise TypeError or
ValueError; expected source/I/O defects return structured failures.

Optional missing/defective GPS does not invalidate usable core motion. Invalid
supplied gravity remains fatal; gravity is never fabricated. Global resource
failures remain fatal even inside unknown or optional content. Unreadable or
oversized inputs have no complete-source digest; no partial read is represented
as complete provenance. Each call owns independent state, so repeated same
bytes/policy produce equivalent output. See [API contracts](../development/IMPORT_SERVICE.md).

## Explorer analysis delivery

The import worker calls the lossless importer, then `present_recording` prepares
one snapshot through `AnalysisService`. Parsing itself does not calculate analysis.
An expected unavailable stage still yields a READY raw-capable snapshot; an import
failure preserves the displayed source and service binding. UI adoption creates
an active service from the validated snapshot without repeating numerical work.

```mermaid
sequenceDiagram
    participant UI as Explorer views
    participant Loader as Import worker
    participant Adapter as AnalysisController
    participant Worker as Smoothing worker
    participant Service as AnalysisService
    UI->>Loader: Open path with load generation
    Loader->>Loader: Lossless import
    Loader->>Service: Prepare complete source snapshot
    Service-->>Loader: Consistent immutable snapshot
    Loader-->>UI: Presentation and load generation
    UI->>UI: Reject closed or superseded load
    UI->>Adapter: Bind prepared snapshot
    Adapter->>Service: Adopt snapshot and subscribe
    Service-->>Adapter: Initial AnalysisState with snapshot and request status
    Adapter->>Adapter: Queue Qt delivery and check active binding on UI thread
    Adapter-->>UI: Initialize matching READY snapshot
    UI->>Adapter: Change smoothing and advance UI intent
    Adapter->>Worker: Queue latest intent
    Worker->>Worker: Skip obsolete or closed binding
    Worker->>Service: Request smoothing synchronously
    Service->>Service: Advance revision and mark dependent stages dirty
    Service-->>Adapter: AnalysisInvalidated(source, revision, dirty stages)
    Adapter->>Adapter: Queue Qt delivery and recheck current request status
    Adapter-->>UI: Show pending only for matching active request
    Service->>Service: Reuse upstream stages and calculate outside state lock
    alt Completion superseded or service closed
        Service->>Service: Discard completion without changing current state
    else Current calculation succeeds
        Service->>Service: Publish complete snapshot and READY state
        Service-->>Adapter: AnalysisUpdated(source, revision, replaced stages, snapshot)
        Adapter->>Adapter: Recheck source intent revision binding and status on UI thread
        Adapter-->>UI: Apply matching snapshot or discard stale delivery
    else Current calculation fails
        Service->>Service: Retain previous snapshot and publish FAILED state
        Service-->>Adapter: AnalysisFailed(source, revision, affected stages, failure)
        Adapter->>Adapter: Recheck source intent revision binding and status on UI thread
        Adapter-->>UI: Clear matching pending status and present failure
        Note over Service,UI: Retained values keep their original configuration and revision
    end
    Note over Service,UI: Running exports retain their previously bound snapshot
    UI->>Adapter: Close or bind another source
    Adapter->>Service: Unsubscribe and close previous service
    Adapter->>Adapter: Reject late queued callbacks and worker results
```

The service calculates synchronously in its caller's thread and owns subscriptions,
not workers or Qt signals. Initial registration/state capture is coordinated:
`AnalysisState` immediately includes source identity, the last completed snapshot
(or None), requested revision/status, dirty stages and failure. Per-registration
queues deliver initial state before later notifications, outside the state lock.
Stage interests filter numerical changes while retaining terminal status for
subscribers that observed pending work. Callback exceptions remove only that
registration. Detailed pending indications may be coalesced after completion.
Technical notifications are distinct from domain `AirtimeEvent` values.

Current requests finish with an update or failure. Failed work publishes no partial
snapshot; the previous snapshot remains identified by its own configuration and
revision. Superseded success/failure cannot replace the current state or clear a
newer request's pending status. The adapter's single worker queue skips obsolete
intents; an intent generation invalidates already queued UI callbacks even before
the newer request reaches the service.

Every queued initial/pending/update/failure delivery is checked again on the UI
thread: active binding/subscription, UI-intent generation, source hash, service
revision and terminal status must still match. A delayed pending message cannot
restore pending after completion; an older initial state cannot overwrite a newer
result. Failure retains displayed values and resets the smoothing control to their
configuration. Close/reopen invalidates load generations and bindings, releases
subscriptions and prevents late imports, errors or results from affecting a new
source. The adapter and service do not accumulate snapshot histories.

Projection, source/time and independent orientation survive smoothing changes.
The explorer refreshes charts, context strip, selected-sample cards, technical
details and visible-range extrema from one guarded delivery. Cursor, selection,
viewport, language and appearance remain presentation state and do not trigger
numerical preparation. Export assistants/previews bind their opening snapshot;
explicit export configuration may prepare a different one using shared stages.
Running exports never follow workspace updates. Snapshot ownership and release
follow the [lifetime concepts](08_concepts.md#snapshot-lifetime-and-reuse).

## Product boundaries

Visible-range extrema update on source/viewport/mode/smoothing changes; the
explicit From/To selection is separate from the viewport.
The explorer's Play/Pause action starts a Qt-independent monotonic sample clock.
A GUI-thread timer adopts its current integer sample through existing navigation;
missed ticks do not accumulate drift. Seeking resets the clock origin. Pause, recording
end, import/replacement, export opening and window close stop timer delivery.
No analysis is recalculated during playback. The persistent ride library and POV
synchronization remain planned.
Frame rendering and encoding are implemented for the 4K overlay slice. Universal physical
rider qualification and analytical GPS are outside current M3 acceptance. This view introduces
no invented runtime interactions for those services.

## Implemented device-only analysis

```mermaid
sequenceDiagram
    participant Caller
    participant Device as analysis.device
    participant Pint as Private Pint registry
    participant NumPy
    Caller->>Device: Full M2 success, explicit UTC time, per-sequence contracts
    loop Acceleration and gravity independently
        Device->>Device: Check source hash, sequence, unit and quantity references
        alt Absent sequence or absent contract
            Device->>Device: UNAVAILABLE channels with ordered warnings, no samples
        else Qualified DEVICE components
            Device->>Pint: Convert one supported component-unit factor to SI
            Pint-->>Device: Explicit SI scale
            Device->>NumPy: Convert owned array, then stable Euclidean norm
            NumPy-->>Device: Owned vectors and magnitude, or finite-range defect
            Device->>Device: Retain usable vectors and report invalid products independently
        end
    end
    Device-->>Caller: Immutable AnalysisResult retaining complete M2 source
```

Caller contract/type/hash defects raise TypeError/ValueError. Expected finite-range
calculation defects produce INVALID products with structured errors. Source
absence and unknown units produce UNAVAILABLE products with different warning
codes. A declaration cannot create absent gravity. The caller supplies calculation
time; sample indices remain indices, with no generated timeline or epoch.
There is no addition/subtraction of the two source channels, no normalization
into rider G, and no calibration, filtering or GPS processing. The registry reads
installed definitions at module initialization; subsequent calculations perform
no file or network access. Caller evidence references are explicit attestations,
not an empirical verification service.

## Explicit provisional frame projection

A separate `analysis.frames.analyze_rider_frame` call checks M2 success, source-bound
calibration, profile/assumption permission and independent device-unit contracts.
Missing mapping/data/units returns excluded channels. An explicit admitted basis
passes through SciPy passive rotation; resulting rider vectors are PROVISIONAL.
Range failures yield INVALID, while other usable sequences remain independent.
It never guesses source axes, normalizes input bases or labels real rider forces verified.
The caller supplies UTC time; no clock alignment, gravity combination or filtering occurs.
See [passive frame decision](09_architecture_decisions.md#passive-frame-transforms).

## Raw explorer interaction

```mermaid
sequenceDiagram
    actor User
    participant Window as Raw explorer
    participant Worker as Qt worker
    participant View as Qt-independent presentation
    participant Importer as M2 import service
    User->>Window: Choose a local recording
    Window->>Worker: Start background load and show progress
    Worker->>View: Load and prepare raw view
    View->>Importer: Read-only import
    Importer-->>View: Full success or structured failure
    View-->>Worker: Immutable axes and source or failure
    Worker-->>Window: Queued completion
    Window->>Window: Show complete x/y/z or retain previous view on failure
    User->>Window: Navigate, zoom and choose an inclusive interval
    Window->>View: Validate local sample selection
```

Cancelling the picker changes nothing. The previous view survives load errors.
Application shutdown drains outstanding worker tasks after the window closes;
it does not kill parsing mid-call. Axis labels use source values/inferred elapsed seconds,
not rider G or a fabricated clock. Qt Charts handles interactive chart drawing;
export frame generation and encoding are separate implemented services.

Background presentation attempts source-direction projection and a configurable centered mean
(default 11) for every successful import. Loading selects calibrated curves by
default; the checkbox switches arrays/value bounds while preserving time/selection.
Expected calibration errors or absent optional NumPy retain raw data and a visible
explanation. Source hashes do not gate availability.

The focus workspace presents loaded curves with current-value cards and a right
inspector. A width breakpoint switches compact windows between chart and inspector;
scroll areas preserve reachable controls without changing chart coordinates.
Global import-note access opens the inspector/details and scrolls to diagnostics
after layout. Card values and clock text refresh from explorer presentation when
sample, calibration or smoothing changes. Technical expansion is independent of
analysis state. All raw/calibrated, failure and worker shutdown paths above remain.

## Sample data export runtime

The explorer pauses playback and captures the current analysis snapshot and From/To
interval before destination selection. Existing destinations require confirmation
after suffix completion, defaulting to No. A shared Qt worker serializes prepared sample
views to CSV or JSON; no analysis or encoding runs in the widget. JSON collects
parallel arrays before incremental encoding. The separate Analyzer JSON option
collects grouped measurement arrays and stores shared time/quality once.
Queued progress and terminal signals
update the modal progress window on the UI thread. Cancellation/main-window close
sets a worker event; incomplete output is removed. Confirmed replacement is written
separately and committed atomically after success; failure preserves the previous
file. Success remembers the existing
export directory and reports the saved path. The bound snapshot stays alive until
worker completion, independently of later workspace updates.

## 4K export runtime

Export snapshots the loaded immutable recording, current smoothing and selected
range/profile/aspect/language. A Qt worker prepares/streams frames to FFmpeg; NVIDIA Vulkan
or NVENC is selected only after an actual encode probe, otherwise CPU is used.
Signals report backend/progress, completion and failure without blocking widgets.
Cancellation or window close sets a thread event; incomplete files are discarded.
The service publishes the completed encoder output exclusively.
No existing file is replaced. The user aligns the
single exported overlay with an Onride clip externally in Resolve.

## Saved batch runtime

```mermaid
sequenceDiagram
    actor User
    participant UI as Batch window
    participant Store as SQLite export store
    participant Queue as Batch worker/service
    participant Encoder as Existing export service
    User->>UI: Run selected or all saved batches
    UI->>Store: Read immutable batch definitions
    Store-->>UI: Source paths, hashes, ranges and preset snapshots
    UI->>Queue: Queue snapshot and unique output root
    loop Each recording/preset job
        Queue->>Queue: Reimport, check hash, prepare saved recipe/range
        Queue->>Encoder: Render and encode one video
        Encoder-->>Queue: Complete output or failure/cancellation
        Queue-->>UI: Progress and per-job result
        Queue->>Queue: Persist incremental run report
    end
```

Expected job failures are recorded and processing continues; cancellation discards
the active incomplete encode and skips remaining jobs. Completed files stay intact.
Close/Escape requests cancellation and never abandons an active encoder. Presets
and definitions survive restart; resume/history services remain outside scope.
