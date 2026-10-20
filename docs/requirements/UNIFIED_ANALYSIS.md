# Unified recording analysis requirements

Status: Implemented and locally validated on native Windows. All seven
implementation areas below are complete. Immutable containers, explicit snapshot
validation, stage preparation, sample access and partial recalculation are provided by
[`analysis.recording`](../../src/ride_forces_analyzer/analysis/recording.py).
Preparation reuses the current source-app projection, centered mean, independent
gravity tilt and vertical-context heuristic; the [API contract](../development/ANALYSIS_MODELS.md#unified-recording-analysis)
defines supported configurations, raw fallback and shared-stage reconfiguration.
The [`analysis.service`](../../src/ride_forces_analyzer/analysis/service.py) implements
state, subscriptions, initial delivery and guarded request success/failure.
The service remains synchronous; the explorer uses a worker/UI-thread adapter
for import handoff, smoothing and guarded delivery. Exports, previews and batch
jobs bind shared immutable snapshots. Separately configured airtime event
detection is implemented. See the current
[runtime architecture](../architecture/06_runtime_view.md#explorer-analysis-delivery).

## 1. New data model as a parallel class structure

The maintained [unified analysis API](../development/ANALYSIS_MODELS.md#unified-recording-analysis)
owns the data/sample interfaces, class diagram and its explanation, configuration,
validation, shared stages, availability, quality and provenance. Detailed source
fields remain in [canonical models](../development/CANONICAL_MODELS.md).
[Chapter 05](../architecture/05_building_block_view.md#analysis-boundary) owns
structural responsibilities; [chapter 08](../architecture/08_concepts.md#scientific-provenance-and-gates)
owns scientific boundaries. Separate [airtime event rules](../implementation/AIRTIME_EVENTS.md)
own event intervals, onset, duration, gaps and provisional interpretation.

## 2. Import integration

The [import handoff contract](../development/IMPORT_SERVICE.md#application-analysis-handoff)
owns lossless parsing and application analysis integration. The
[analysis API](../development/ANALYSIS_MODELS.md#unified-recording-analysis) owns
partial recalculation and subscription methods. The
[runtime view](../architecture/06_runtime_view.md#explorer-analysis-delivery) owns
the notification sequence and explanation, initial delivery, dirty/update/failure
completion, stale work and UI-thread checks. The
[lifetime concepts](../architecture/08_concepts.md#snapshot-lifetime-and-reuse)
own retained snapshots, stage reuse and reference release.

## 3. Application output

The [explorer contract](../implementation/RAW_EXPLORER.md) owns charts, cards,
technical details, raw display, context strip, visible-range extrema, navigation,
selection, metadata/GPS and localization. The
[context contract](../implementation/AIRTIME.md) owns prepared categories,
stabilization and scientific limits; [runtime architecture](../architecture/06_runtime_view.md#explorer-analysis-delivery)
owns consistent guarded delivery to the views.

## 4. Export integration

The [video contract](../implementation/VIDEO_EXPORT.md) and
[layout API](../development/EXPORT_LAYOUTS.md) own full-history analysis,
independent orientation, snapshot binding, interpolation/context lookup and separate
frame generation/encoding. The [batch contract](../implementation/EXPORT_BATCHES.md)
owns complete recipes, source identity checks and saved job snapshots. The
[analysis API](../development/ANALYSIS_MODELS.md#unified-recording-analysis) owns
configuration-bound stage reuse. Context and event semantics remain in their
separate [context](../implementation/AIRTIME.md) and
[event](../implementation/AIRTIME_EVENTS.md) contracts.

## 5. Implementation status

All seven areas are implemented and locally validated.

1. Model validation, availability states and source/time correspondence: implemented
   through explicit snapshot validation. Constructors do not validate automatically.
2. Initial projection, independent orientation, smoothing, context and sample views:
   implemented using shared numerical functions and sample views, with independent
   source-app evidence and numerical contract tests.
3. Partial recalculation and bounded snapshot lifetime: implemented through shared
   stages, unchanged prior snapshots and no retained snapshot/configuration history.
4. Service state, subscriptions, initial delivery and revision/error handling:
   implemented with synchronous calculations, guarded completion and callback cleanup.
5. Import/explorer integration and UI-thread adapter: implemented with shared
   prepared buffers, background smoothing and stale-result/lifetime guards.
6. Export, preview and batch integration: implemented with bound shared snapshots,
   prepared orientation/context and complete, explicit persisted analysis recipes;
   incomplete stored records are rejected without data removal.
7. Separate airtime event rules and detection: implemented as opt-in version-1
   episodes with provisional categories, source intervals, onset and coverage flags.

### Local validation status

The supported implementation, tests/reference tools and migrated documentation
are validated on native Windows, Python 3.14.6 and Qt 6.12.0:

- `uv run --locked pytest`: **1,852 passed**, including scientific evidence,
  model/service, export, storage, reference-tool and UI contracts.
- Required [project checks](../development/SETUP.md): lock consistency, Ruff lint
  and formatting, mypy, Pyright, type contracts (**11 passed**), dependency
  contracts (**20 passed**) and CI selection contracts (**45 passed**) pass.
- `npm run test:docs`: Markdown, spelling and documentation links
  (**51 passed**) pass for the migrated content.

The unchanged model/service coverage inputs retain **100% statement and branch
coverage** from the **201-test**
[coverage gate](../development/CODE_QUALITY.md#recording-model-and-service-coverage).
This is reused coverage evidence, not a new coverage run. Temporary outputs remain
under `.tmp/`. Local checks do not qualify frozen release packages or establish
hosted CI results.

Scientific interpretation and event thresholds retain their documented provisional
status; event detection requires explicit configuration.

## 6. Planned requirements for complete legacy removal

Status: Contract ownership, the current legacy-consumer inventory, numerical
preparation consolidation and direct explorer/extrema consumption are implemented.
Export/storage APIs use explicit snapshots and complete stored recipes.
Obsolete runtime implementations and their comparison-only consumers are removed.
Tests and reference tools use supported APIs and independent expected results.
Durable contracts and diagrams have maintained API/product/arc42 destinations;
native Windows and documentation checks pass for the supported implementation.
Steps 1–7 are complete; step 8 remains planned. The implemented scope in section 5
is complete, with the unified model as the sole production analysis path.
No backward compatibility is required for previous APIs, data representations,
presets or batch formats. Do not retain compatibility facades, aliases, wrappers,
old calculation paths or obsolete tests. Raw display and explicitly unavailable
analysis results remain supported product behavior, not legacy fallbacks.

### Contract ownership

The maintained destinations below own the contracts from sections 1–4. Both
Mermaid diagrams and their explanations are in their designated API/runtime owners;
this document retains links until its final removal in step 8.

| Retained contract                                                                                                            | Maintained owner                                                                                                                                                                                                                                                                              |
| :--------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data and sample API; configuration; validation; shared stages; availability; quality and provenance (sections 1–2)           | [Analysis models](../development/ANALYSIS_MODELS.md): authoritative API contracts, including the class diagram and the explanation of its relationships and stage sharing.                                                                                                                    |
| Lossless import and application analysis handoff; expected unavailable stages versus import/calculation failures (section 2) | [Import service](../development/IMPORT_SERVICE.md#application-analysis-handoff) and [runtime architecture](../architecture/06_runtime_view.md#explorer-analysis-delivery): parsing stays independent; the worker/service prepares one coherent snapshot and preserves prior views on failure. |
| Layering, component responsibilities and numerical/service/presentation boundaries (sections 1–4)                            | [Arc42 chapter 05](../architecture/05_building_block_view.md): structural architecture and dependencies; link detailed API/product contracts.                                                                                                                                                 |
| Service state, subscriptions, initial delivery, dirty/update/failure completion and worker/UI delivery (section 2)           | [Arc42 chapter 06](../architecture/06_runtime_view.md): notification sequence diagram and its explanation, including stale deliveries, shutdown and bound export snapshots. Public service signatures remain in the analysis API guide.                                                       |
| Source/time correspondence, raw and missing data, units/axes, scientific boundaries and snapshot lifetime (sections 1–2)     | [Arc42 chapter 08](../architecture/08_concepts.md): shared concepts and invariants. Detailed source/import fields remain in [canonical models](../development/CANONICAL_MODELS.md) and the [import service](../development/IMPORT_SERVICE.md).                                                |
| Workspace charts, context strip, sample cards, technical details, extrema and view state (section 3)                         | [Explorer contract](../implementation/RAW_EXPLORER.md): user-visible behavior; calculation APIs remain in the analysis guide.                                                                                                                                                                 |
| Full-history preparation, bound exports/previews, interpolation and rendering/encoding separation (section 4)                | [Video export](../implementation/VIDEO_EXPORT.md) and [layout API](../development/EXPORT_LAYOUTS.md): output behavior and renderer interfaces.                                                                                                                                                |
| Explicit analysis recipes, source identity checks and sequential job behavior (section 4)                                    | [Batch contract](../implementation/EXPORT_BATCHES.md): preset/job persistence and execution behavior.                                                                                                                                                                                         |
| Separate context and domain-event semantics, provisional thresholds, onset, duration and gaps (sections 1–4)                 | [Airtime context](../implementation/AIRTIME.md) and [airtime events](../implementation/AIRTIME_EVENTS.md): distinct domain/product rules; the analysis guide owns result types.                                                                                                               |
| Executable validation commands, coverage scope and current verification evidence (section 5)                                 | [Code quality](../development/CODE_QUALITY.md) and [Windows setup](../development/SETUP.md): maintained verification workflows. Retain relevant current evidence without copying a historical implementation report.                                                                          |

The sections 1–4 coverage is complete: model/stage/sample contracts and their
class diagram belong to the analysis API; import handoff and notifications to the
import/runtime owners; lifetime/time/scientific limits to chapter 08; and visible
behavior, export recipes, context and event rules to the listed product contracts.
Both diagrams describe the implemented ownership and scheduling, rather than a
parallel proposed architecture. No scientific rule or recording permission is
owned solely by this requirements document.

Retain the [source-app projection decision](../architecture/09_architecture_decisions.md#source-app-projection),
[physical qualification boundary](../architecture/09_architecture_decisions.md#physical-qualification)
and other applicable ADR references in chapter 09. The
[source comparisons](../validation/APP_REFERENCE.md) remain the owner of scientific
evidence and known recording-specific differences. The
[recording catalog](../development/RECORDINGS.md) and
[fixture attribution/license](../../tests/fixtures/real/README.md) retain recording
authorization, identities and publication conditions. A container's removal must
not discard this evidence or expand its scientific qualification.

### Current dependency inventory

Production consumers use unified source/stage/sample contracts and complete stored
recipes. Projection and smoothing retain their permanent numerical owners;
orientation, context and events retain their dedicated analysis modules.
Scientific evidence tests use `RecordingAnalysis` and independently documented
expected values. No legacy runtime consumer remains in the reviewed scope.

Existing validated domain/import models, explicit device/frame analysis, immutable
sample buffers, the analysis service, Qt delivery adapter and read-only renderer
views remain supported contracts. Their age or use of an adapter does not make
them compatibility code. Preserve raw operation, independent GPS and source-bound
scientific limits when removing the inventoried dependencies. Requirement 8
below governs final removal after validation; this inventory does not require absence tests.

### Ordered removal steps

1. **Assign ownership of the retained contracts.** Ownership and the current
   consumer inventory are defined in the tables above. Keep those assignments
   authoritative while steps 2–8 migrate consumers and durable knowledge. Retain
   existing ADR, source-evidence and recording-authorization references.

2. **Consolidate numerical preparation.** Implemented: projection and smoothing
   have permanent numerical owners; orientation, context and configured events
   retain their existing dedicated modules. Keep one implementation of projection,
   smoothing, independent orientation, context and configured event detection,
   consumed through `RecordingAnalysis` and the analysis service. Move still-needed
   numerical primitives out of legacy modules into their permanent analysis owners
   before removing those modules. Preserve source-axis polarity, inferred time,
   filter edges, immutable buffers, missingness and provisional scientific meaning.
   The source-app projection policy remains distinct from qualified physical-frame
   analysis; removing a legacy container must not remove that scientific contract.

3. **Remove the explorer/extrema compatibility path.** Implemented: explorer,
   extrema, UI controls and affected reference tools consume unified stages and
   configuration; missing samples retain unavailable presentation. Make charts, sample cards,
   context, technical details and extrema consume the unified source, stages and
   sample views directly. Remove `ExplorerData.reference`, `_analysis_reference`,
   its `AppReference` construction, and numerical fallback branches. Keep
   `ExplorerData` only for actual presentation/view state. Preserve raw operation,
   metadata, source markers, independent GPS, selections, navigation and localization.
   Retain service subscriptions, initial delivery, revision/error handling and
   UI-thread checks without retaining an old analysis API behind them.

4. **Make export and storage APIs unambiguous.** Implemented: export/preview/job
   preparation requires snapshots, batches import/analyze without presentation
   objects, and stored settings/recipes require complete current fields.
   Export preparation, previews,
   batches and layouts must accept their designated unified analysis input without
   dual legacy/presentation signatures. Remove compatibility handling such as
   accepting `ExplorerData` merely to extract its snapshot. Require the current
   explicit analysis recipe in saved presets/jobs and remove legacy defaults and
   format adapters. Previous persisted formats need not remain readable; unsupported
   records may be rejected clearly without automatic destructive database cleanup.
   Preserve full-history analysis, interpolation, context lookup, independent
   orientation, bound export snapshots and separate frame generation/encoding.

5. **Delete obsolete implementations and public surfaces.** Implemented: the
   obsolete reference module and temporary runtime-parity test are removed;
   scientific evidence tests exercise unified snapshots directly. Once their
   consumers are migrated, remove `AppReference`, `reconstruct_app_reference`,
   `smooth_reference` and any remaining compatibility-only helpers, overloads,
   imports and exports. Remove emptied legacy modules after relocating legitimate
   shared primitives. Do not replace removed interfaces with forwarding facades
   or keep a second implementation for comparison. Review remaining consumers
   directly; no separate absence-checking framework is required.

6. **Consolidate tests and reference tools.** Implemented: scientific assertions
   exercise unified snapshots, reference tools and smoke checks use supported
   entry points, and coverage commands/documentation target current tests.
   Remove obsolete legacy/API-compatibility
   tests and tests comparing the new runtime against retained old runtime code,
   including the temporary Taron migration-parity test. Preserve useful scientific
   and behavioral assertions as tests of the supported implementation, using
   independent expected results or existing authorized evidence where appropriate.
   Update screenshot/reference generators, smoke checks, coverage commands and
   documentation links to the supported APIs. Keep fixture bytes and licensing
   unchanged. Do not add tests whose purpose is proving removed symbols, files or
   branches are absent; test current behavior and public contracts instead.

7. **Migrate and validate the durable documentation.** Implemented: contracts,
   both diagrams and their explanations are consolidated in their maintained
   owners. Sections 1–4 have complete destination coverage; native Windows and
   final documentation checks pass.
   Preserve the class diagram
   and its explanation in the analysis API documentation. Preserve the notification
   sequence diagram and its explanation in the runtime architecture, including
   initial state, dirty/update/failure completion, stale work, UI-thread delivery
   and snapshot ownership. Update diagrams to the final implementation while
   retaining these semantics. Keep architecture exclusively within arc42 chapters;
   do not create a parallel overview. Migrate remaining product requirements to
   [explorer](../implementation/RAW_EXPLORER.md),
   [export](../implementation/VIDEO_EXPORT.md),
   [batch](../implementation/EXPORT_BATCHES.md),
   [context](../implementation/AIRTIME.md) and
   [event](../implementation/AIRTIME_EVENTS.md) contracts as applicable.
   Consolidate existing descriptions rather than duplicate them or preserve a
   migration diary. Verify all requirements in sections 1–4 have a maintained
   destination, with diagrams, explanations and scientific limitations intact.
   Complete native Windows checks for the final supported implementation and run
   the documentation checks against the migrated content.

8. **Remove this requirements document last.** Only after the legacy removal and
   knowledge migration are complete, delete `docs/requirements/UNIFIED_ANALYSIS.md`
   entirely. Update the documentation index and all references/anchors to point
   directly to the maintained destinations. Do not retain an archived copy,
   replacement requirements overview or historical completion report. Verify
   documentation links after deletion; the final state consists of the supported
   implementation, its relevant tests and the maintained product/API/architecture
   documentation, including both diagrams and their explanations.
