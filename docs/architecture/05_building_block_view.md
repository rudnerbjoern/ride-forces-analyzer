# 5. Building Block View

[Architecture index](README.md)

## White box: overall system

```mermaid
flowchart TB
    Entry["__main__.main"] --> Settings["config.AppSettings"]
    Entry --> Qt["Raw explorer window and Qt Charts"]
    Qt --> Worker["Background load transport"]
    Worker --> Presentation["explorer: raw view and local selections"]
    Presentation --> Service
    Presentation --> Domain
    Service["importers.service"] --> Decoder["importers.decoder"]
    Service --> Motion["importers.motion"]
    Service --> Optional["importers.optional"]
    Service --> Budget["Per-call diagnostic budget"]
    Service --> Results["Import results and diagnostics"]
    Decoder --> Domain["Immutable domain / source models"]
    Motion --> Domain
    Optional --> Domain
    Results --> Domain
    Analysis["analysis.models: implemented contracts"] --> Domain
    Analysis --> Results
    Analysis --> NumPy["NumPy immutable byte-backed array views"]
    Device["analysis.device: explicit vectors / norms"] --> Analysis
    Device --> NumPy
    Device --> Pint["Pint: validated unit conversion"]
    Frames["analysis.frames: explicit provisional frame vectors"] --> Device
    Frames --> Analysis
    Frames --> SciPy["SciPy: passive frame rotation"]
    Storage["storage: SQLite export definitions"] --> Rendering
    Qt --> Playback["playback: monotonic sample clock"]
    Rendering["rendering: 4K frames / encoder / batches"] --> Recording["analysis.recording: shared snapshots"]
    Rendering --> Service
    Rendering --> AnalysisService["analysis.service: state and subscriptions"]
    Presentation --> Recording
    Presentation --> AnalysisService
    Qt --> Adapter["ui.analysis: worker and UI delivery"]
    Adapter --> AnalysisService
    AnalysisService --> Recording
    Recording --> Analysis
    Recording --> Numerical["source projection / mean / tilt / context / events"]
    Numerical --> NumPy
```

Arrows express dependencies. Dashed arrows describe future consumers, not
implemented services. The explorer starts import through a background worker;
widgets contain no parser, scientific transformations or source mutation.

## Contained building blocks

| Block                | Responsibility and interface                                                                    | Status / source location                                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Bootstrap / settings | main validates AppSettings before creating the Qt window                                        | Implemented: [entry point](../../src/ride_forces_analyzer/__main__.py), [settings](../../src/ride_forces_analyzer/config.py) |
| domain               | Recording, SourceEnvelope, SourceNumber, vectors, motion, metadata, attributes and GPS concepts | Implemented immutable representations: [domain](../../src/ride_forces_analyzer/domain/)                                      |
| importers            | Strict decoding, motion/optional validation, ordered diagnostics and public import composition  | Implemented: [importers](../../src/ride_forces_analyzer/importers/)                                                          |
| analysis             | Immutable contracts, device/frame math and source-app projection/mean                           | Implemented analysis services: [analysis](../../src/ride_forces_analyzer/analysis/); basic extrema implemented               |
| storage              | SQLite export presets and batch snapshots                                                       | Implemented export configuration                                                                                             |
| playback             | Monotonic sample clock, 0.5×/1×/2× speed, pause and seek                                        | Implemented: `playback.clock.SamplePlayback`                                                                                 |
| rendering            | Independent RGBA generation and FFmpeg encoding                                                 | Implemented five-profile landscape/portrait transparent/opaque video                                                         |
| ui                   | Raw chart controls and background import/export transport                                       | Implemented raw/calibrated explorer and sample playback                                                                      |

## Importer composition and interfaces

`decoder` performs bounded Path/bytes input, lexical preflight and strict JSON
dispatch to schema 2.2.0 or the explicit unversioned RFDB profile. `motion`
validates components, paired lengths, independent indices
and structural vectors. `optional` parses metadata, arbitrary ordered attributes
and indexed GPS slots. `service` composes these workers with one per-call
`DiagnosticBudget`; `result`/`diagnostics` expose immutable tagged outcomes.
Only full-service success supplies a complete Recording.

Use the [public Path/bytes API](../development/IMPORT_SERVICE.md). Standalone
[decode](../development/STRICT_DECODING.md), [motion](../development/MOTION_PARSING.md)
and [optional](../development/OPTIONAL_PARSING.md) APIs establish subset contracts.
The [domain guide](../development/CANONICAL_MODELS.md) defines owned bytes/tree,
source scalars, tuple collections and absence/default provenance.

## Analysis boundary

[Analysis models](../development/ANALYSIS_MODELS.md) retain full M2 ImportSuccess,
immutable NumPy data, provenance and independently bounded channel indices.
Opt-in `analysis.device.analyze_device_vectors` accepts source-bound
MotionUnitContract declarations and returns independent SI vectors/norms.
It never runs automatically after import. Library calls stay behind this API;
caller references do not certify source semantics.

`analysis.frames` supplies strict explicit-basis validation, passive
SciPy transforms and source-bound opt-in PROVISIONAL rider vectors. No real rider
calibration is qualified by this strict API. Its universal qualification and general
statistics are deferred; GPS analytics is outside the implemented
[analysis boundary](08_concepts.md#scientific-provenance-and-gates).
The boundary stays independent of widgets, storage and encoding. All five fixtures
participate in capability tests, including absent Watch gravity/GPS. Deeper future
services are documented only when designed.

`analysis.projection` owns source-app direction normalization and dot projection;
`analysis.smoothing` owns the centered mean and recording-edge policy. These are
separate from the qualified physical-frame APIs. `analysis.orientation` owns
independent source-gravity tilt; `analysis.airtime` owns display-context rules.
`analysis.calibration` admits fixed acceleration references and builds the
source-bound provisional basis; it does not mutate the imported recording.
Projection and smoothing have one implementation each, consumed through unified
snapshots. Scientific comparison tests exercise these snapshots against the
retained original-file and screenshot evidence.

`analysis.recording` contains the parallel unified recording-analysis model,
reusing existing contracts. Explicit snapshot validation checks source,
time, availability, payloads and shared dependencies without numerical calculation.
Initial preparation uses these shared projection, smoothing, independent orientation
and context functions, plus configured event detection. Sample views read the prepared buffers without recalculation.
Reconfiguration reuses stages with matching configuration and input references;
smoothing retains the original projection and independent orientation. Snapshots
bind their optional calibration basis to projection; orientation depends only on
the Gravity choice. The existing service invalidates the affected stages when
Gravity or Incline changes. Snapshots retain stages, not prior snapshots or a
configuration history.
`analysis.events` evaluates explicitly configured provisional airtime episodes
from the selected vertical force stage. Its versioned rules are independent of
context confirmation/hysteresis, retain missing-data and boundary limits, and
reuse the existing event containers and partial recalculation dependencies.
The explorer and export consumers read shared snapshots and stage buffers.
`ExplorerData` owns view state, formatting and read-only chart views; cards and
technical sample values read snapshot sample views. Context labels/strip segments
format prepared categories without a second context calculation. Extrema consume
`SmoothedForces` directly, retaining quality, provenance and source/time identity.
Raw display remains available without derived forces or an optional NumPy runtime.
`analysis.service` manages coherent state, subscriptions with immediate initial
delivery, partial analysis requests, revision/error handling and cleanup. Numerical
work and serialized per-subscriber callbacks run outside its state lock. Superseded
completions cannot replace current state, and old queued deliveries are discarded.
The service owns no worker, snapshot history or Qt/storage dependency.
`ui.analysis.AnalysisController` owns worker scheduling and queued UI delivery,
checking source, revision, terminal state, active binding and UI-intent generation
when applying results. `ui.loading` carries a load generation so closed/reopened
windows reject older imports and errors.

`gps_overview` prepares immutable approximate spatial reference segments from
independent source GPS slots, preserving gaps and source ownership. `ui.gps`
renders these in a separate dialog, enabled only for usable positions. Original
geographic segments retain the same missing-fix/time-gap boundaries. `map_background`
projects them to Web Mercator for consistent route/raster alignment, derives a visible
tile request and owns bounded HTTPS/image composition. `storage.map_tiles` stores
PNG bytes and HTTP validators in a separate, bounded SQLite tile cache. `ui.gps` transports
that request through a worker and applies only current results. Without supported
map coordinates, the original local WGS84 approximation remains available.
The geometry has no dependencies on force analysis, sensor time or local selections.

`ui.application.RecordingApplication` owns recording windows and their open-request
queue. `instance.InstanceBroker` owns process locking and local Qt IPC, with no
widget or analysis dependency. `__main__` coordinates ownership before window
creation. Each `ui.window.ExplorerWindow` retains its own import/analysis controller
and presentation state; only application preferences are shared across windows.

The focus workspace keeps Qt-only structure in `ui.window` and local
styling in `ui.theme` and native caption/icon integration in `ui.chrome`. Qt-independent `explorer` supplies compact header text,
ordered metadata rows, sample clocks and directional current-value cards from
unchanged presentation data. Split/scroll/expand state is view-only; no scientific
or import operation moves into widgets. The separate GPS dialog is retained.

Basic per-axis extrema for inclusive selections are implemented in the pure
`force_extrema` module, with immutable source/mode/window/unit/index/time results.
Explorer presentation exposes them in the inspector; widgets perform no calculation.
Raw operation avoids importing the NumPy-backed analysis package. This is a small selected-range product, not a generic statistics engine.

## Sample data export boundary

`csv_export.export_csv` and `json_export.export_json` serialize one bound `RecordingAnalysis` and an inclusive
source interval. `json_export.export_analyzer_json` provides a separate versioned
format with grouped arrays, shared time/quality and scientific configuration.
Numerical preparation and sample correspondence stay in analysis;
the serializers have no Qt, frame-generation or video encoder dependency.
`_export_file` owns exclusive creation and atomic replacement of confirmed exports.
`ui.data_export` owns shared worker transport and progress/cancellation UI. The explorer
captures snapshot/range before the save dialog; later workspace changes cannot
change that export. See the [CSV contract](../implementation/CSV_EXPORT.md) and
[JSON contract](../implementation/JSON_EXPORT.md).

## Video export boundary

Export preparation/previews accept `RecordingAnalysis`; layouts consume a bound
`ExportTimeline`. Batches depend on import/analysis services and persisted recipes,
not explorer presentation. Stored recipes and video settings are complete and
explicit; unsupported records are rejected while preserving database contents.

Export timelines bind one immutable `RecordingAnalysis`. Read-only channel views
share prepared buffers, and layouts read prepared orientation/context without
recalculation. Previews share that snapshot across profiles; running exports never
adopt later workspace changes. Presets persist recipes, never sample arrays.
Saved settings resolve implicit placement to a named layout/format position;
immutable job snapshots retain it through batch execution. Geometry stays in layouts.

The [Manta G-Orbit video example](https://youtu.be/tsRzD416voU) shows the exported
overlay composed over Onride footage.

`analysis.orientation` implements source-gravity-to-vertical tilt with missing/zero
vectors retained as gaps. `rendering.model` binds source identity, smoothing,
inclusive ranges and fixed per-panel bounds to an independent video frame clock.
`analysis.airtime` prepares immutable, causal presentation labels from smoothed
vertical source g and recent load changes. Compact chart renderers consume these
labels independently of video fps and seek order.
`ExplorerData` also exposes source-index label ranges for the workspace;
Qt maps their time bounds to the clipped, zoom-dependent context strip and
uses the current label in the vertical value card. The
[provisional thresholds and limits](../implementation/AIRTIME.md) do not establish
scientific qualification or a general ride-event analysis service.
`rendering.layouts` provides one module per built-in profile and an explicit
registry of immutable layout metadata and factories. Each plugin owns explicit
position/region mappings and a supported default for each format; registration
validates integer geometry and canvas bounds. The registry resolves the selected
position or format default consistently for frame composition, previews and
encoder padding. Each renderer implements
the same native-RGBA-region/source-position protocol. Shared drawing primitives
and a three-channel chart base support the related compact profiles; G-Orbit and
Column draw independently. `rendering.frames` selects the registered renderer and
composes its region into a full RGBA frame, without layout-specific drawing branches.
Each profile owns its documented design constants, including typography, geometry,
palette and stroke widths. Shared chart algorithms consume profile-specific values;
portrait variants retain their own profile's styling rather than another layout's.
`rendering.peaks` prepares immutable signed peak-hold envelopes from the selected
source interval for G-Orbit. Hold/release follows source time, so random preview
seeks and video-rate changes do not depend on prior render calls.
`ExportSettings` owns landscape/portrait dimensions. Shared region geometry drives
frame composition and encoder padding; portrait force cards reflow vertically.
Previews downsample the complete canvas proportionally. SQLite preset/job snapshots
retain the explicit aspect and complete analysis recipe. Incomplete stored formats
are rejected without migration or destructive cleanup.
The ribbon, corners, HUD and orbit preserve translucent panels and
opaque data. `rendering.encoding` probes NVIDIA Vulkan/NVENC, streams the selected
bounded region to FFmpeg and publishes one
new output exclusively. No GPU or codec operation changes the source clock/data.
`rendering.preview` prepares five exact-source-sample snapshots with the production
renderer and preview-only contrast backgrounds, independent of FFmpeg and Qt.
The [layout API guide](../development/EXPORT_LAYOUTS.md) documents registration,
stable persisted keys and extension rules; plugins are built in, not discovered
or installed dynamically.
Out-of-range cursors are flagged without clamping. `ui.export` owns the two-step
assistant, image transport, debounced/revision-gated preview jobs, queued progress and cooperative cancellation;
no renderer/encoder logic lives in widgets. See [export contracts](../implementation/VIDEO_EXPORT.md).

`storage.export_models` owns versioned immutable presets, source-bound jobs and
batch definitions. `storage.exports` owns SQLite schema/version protection,
transactional writes and the per-user database path. `rendering.batches` validates
source identity and applies complete saved analysis recipes/ranges before sequential exports;
its run report distinguishes completed, failed, cancelled and skipped jobs.
`ui.batches` edits saved queues and transports worker results. No recording bytes
or rendered media enter SQLite; preset changes cannot alter stored job snapshots.
