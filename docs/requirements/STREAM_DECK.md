# Stream Deck integration

<!-- cspell:words Elgato streamdeck -->

Status: Windows application routing, keys and Plus/Neo profiles implemented.
Library/navigation/marker dials, Neo marker editors and contextual InfoBar are
prepared with automated checks. Local Windows installation/startup and profile
import for an attached Plus are verified; physical device operation remains open.

## Confirmed scope

- Windows first, with Stream Deck + and Neo available for development and testing.
- Minimum Stream Deck software version: 7.6.
- macOS compatibility where feasible; support remains unverified until native checks pass.
- Integration: separate plugin and local control interface; no hotkey simulation.
- Plugin: official Elgato TypeScript SDK (`@elgato/streamdeck`), using Stream Deck's Node.js runtime.
- Preferred transport: loopback WebSocket with the same protocol on Windows and macOS.
- Application setting: **Enable Stream Deck**, off by default and persisted
  in user preferences; the control server runs only while enabled.
- Stream Deck + and Neo use the [menu hierarchy](#menu-structure) below.
- Application control is foreground-only; no operation while another application has focus.
- The currently active Explorer is the control target; no active Explorer means
  application controls are unavailable.
- Library controls browse existing entries and explicitly open the selected entry.
- Requested Plus marker-page order, left to right: Start, Gravity, Incline, End.
- Marker interaction: turn to preview, press to apply, tap the touch field to discard its preview.
- Provide dynamic icons, activation/availability feedback and useful state or values
  on keys, the Plus touch strip and Neo InfoBar where supported.
- Selection Start/End dials, shared Fine/Coarse and Zoom to selection are included;
  selection bounds remain separate from recording markers.
- The [initial action scope](#action-scope) is confirmed.
- Distribution: one `.streamDeckPlugin` asset on Analyzer GitHub releases, with
  device-specific Plus and Neo profiles.
- Implemented scope covers loopback transport, typed control contract, application
  actions, keys, native menu profiles, Plus dial/touch controls, Neo marker editors
  and InfoBar feedback. New device controls are prepared without installation.

## Goal and constraints

Optional Library and Explorer control from Stream Deck, with application-state feedback where useful.

- Application processing remains offline and independent of Stream Deck.
- Commands reuse existing actions, validation and analysis services.
- Original recordings remain read-only; no separate force calculations in the plugin.
- Development follows the existing [platform constraints](../architecture/02_architecture_constraints.md).

## Existing basis

Device commands use existing GUI/service actions through the
[typed loopback control contract](../architecture/06_runtime_view.md#stream-deck-control-contract).
The application owns visible Library order, bounds, playback and marker adoption;
the plugin displays confirmed snapshots. Device controls follow the
[stepping and playback rules](#stepping-and-playback).

## Model support

| Available device                         | Controls                                                     | Planning role                                          |
| ---------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------ |
| Stream Deck +                            | Eight keys, four push dials and touch strip                  | Primary development and dial/touch testing             |
| Stream Deck Neo                          | Eight keys, InfoBar and two Touch Points for page navigation | Key-only operation, pages and optional InfoBar testing |

Use shared logical actions with device-specific profiles. The Plus profile uses
dials without duplicate keys or key-editor folders, except for a dedicated
Play/Pause key alongside the Position dial press; Neo uses
key controls. Other models remain possible but unverified. Simultaneous use
of both devices is an open choice, not a prerequisite.

Neo InfoBar actions are display-only and receive no input events. Custom feedback
requires SDK 3.
Keep the normal page navigation separate from plugin status displays.

## Device controls

Assignments below match the prepared native profiles. Native Windows startup,
Analyzer connection and profile import for an attached Plus are verified. Physical
key/dial/touch interaction and Neo hardware behavior remain open.

### Menu structure

Confirmed Stream Deck + and Neo hierarchy:

```text
Start
├── Library
│   ├── Browse / Open
│   └── Import
└── Explorer
    ├── Playback
    ├── View / Curves
    ├── Selection (Plus)
    └── Markers
        └── Start · Gravity · Incline · End (Neo key editors)
```

Back uses top-left (key 1) and Home bottom-right (key 8) in both native profiles.
Stream Deck forces native folder Back to key 1 on import; the preferred key 5
position is not supported. Number keys left to right, top row first.
Start has native App/Website actions around Library/Explorer and no Back/Home keys.

Use bundled device-specific profiles with native nested folders and pages,
rather than a custom menu engine. Profiles can include the agreed key, dial and
display assignments. Plugin-driven navigation can switch bundled profiles and
pages; it cannot switch to arbitrary user-created profiles. Home switches the invoking
device to its bundled Start page. Plus keys provide menus, Import, Play/Pause, curves and
Fine/Coarse; Library browsing/opening, playback/navigation and marker editing
use its dials. Neo retains key controls and marker-editor folders.
Changing menus must not silently confirm marker previews or change the target window.

### Library navigation

- Plus: rotate a dial to select the previous/next entry; press it to open the selection.
- Neo: Previous entry, Next entry and Open keys provide the same actions.
- Move exactly one visible entry per dial notch or key press, without acceleration
  or a coarse mode.
- Both devices: an Import key opens the existing file-import dialog and uses the
  application's Library import workflow.
- Navigation wraps on both devices: Next after the last entry selects the first;
  Previous before the first selects the last. A single entry remains selected;
  an empty list has no selection.
- Browsing changes selection only; opening requires the explicit press/key action.
  Show the selected entry in the Library and in device feedback; opening is unavailable
  without a valid selection.
- Open the selected entry in the current Explorer window; never create a new window.
- Follow the Library's current visible sort order and filters; skip hidden entries.

### Navigation page

| Plus dial | Rotate                                | Press                  | Touch-strip feedback        |
| --------- | ------------------------------------- | ---------------------- | --------------------------- |
| Position  | Step samples or scrub time            | Play/pause             | Replay time or sample       |
| View      | Time zoom around an agreed anchor     | Reset view             | Visible time interval       |
| Playback  | Select an existing playback speed     | Return to normal speed | Actual speed and play state |

Playback uses dial positions 1, 2 and 4; position 3 is unassigned. Smoothing uses
the first dial on View / Curves, alongside force-line and Raw/Calibrated keys.
Its existing odd window range is 1–51 samples: outward turns stay at the minimum
or maximum without wrapping. Press resets to 11. Raw mode remains unfiltered and
disables smoothing; the field identifies raw source values.

### Stepping and playback

Plus defaults to fine mode. A dedicated Fine/Coarse key
switches the position and marker dial step size; the touch fields show the mode.
Marker dial presses still apply the corresponding preview. Neo uses the separate
`- coarse / - fine / + fine / + coarse` keys shown below.

- Position and marker previews: fine = one source sample; coarse = ten source samples
  per dial notch/key press, without acceleration. Stop at valid bounds; only Library
  navigation wraps. Show recording time alongside the sample index.
- Pause on the first manual position change or marker-preview adjustment during
  playback. Applying or discarding a marker does not resume playback; Play resumes it.
- Curve/view changes, zoom and speed selection leave playback running.
- Smoothing and speed controls move to the next existing supported setting.

### Plus mockups

Prepared profile key placement and dial/touch assignments, following
the supported Back/Home positions. Each page
has two key rows, followed by four touch fields and four dials where assigned.
Blank positions are unassigned; menu-only pages leave touch fields/dials unassigned.
Function-specific icons use shape/color status badges; physical legibility and
owner acceptance remain open.

Start:

```text
[ Start app ] [ Library ] [ Explorer ] [ Website ]
[           ] [         ] [          ] [         ]
```

Start app uses Elgato's native Open action with the packaged Analyzer icon. The
user selects the installed EXE or a Windows shortcut in its native settings;
the portable profile leaves the path empty. Discovery contains port/token only,
so it cannot supply an executable path. Website uses Elgato's native Website
action with a bundled colored globe icon and the project URL from the plugin manifest. Both work independently of
the Analyzer connection and do not send control-protocol commands.

Library:

```text
[ Back   ] [ ] [ ] [      ]
[ Import ] [ ] [ ] [ Home ]
Touch: [ Selected entry ] [ ] [ ] [ ]
Dials: [ Browse / Open  ] [ ] [ ] [ ]
```

The first Library dial rotates through entries cyclically and opens on press.

Explorer:

```text
[ Back ] [ Playback ] [ Curves    ] [      ]
[      ] [ Markers  ] [ Selection ] [ Home ]
```

Playback, with the assignments in [Navigation page](#navigation-page):

```text
[ Back ] [               ] [ ] [      ]
[ Play ] [ Fine / Coarse ] [ ] [ Home ]
Touch: [ Time/sample + mode ] [ View interval ] [ Speed/state ] [ ]
Dials: [ Position           ] [ View          ] [ Speed       ] [ ]
```

View / Curves:

```text
[ Back      ] [ Curve 1 ] [ Curve 2  ] [ Curve 3 ]
[ Data mode ] [         ] [ Combined ] [ Home    ]
Touch: [ Smoothing window ] [ ] [ ] [ ]
Dials: [ Smoothing        ] [ ] [ ] [ ]
```

Plus keeps related commands above their dial columns: Import above Library,
Play above Position, Data mode above Smoothing, and selection controls above its
two bounds. Playback dials occupy the first three columns without a gap. Explorer
folders form a central 2×2 group. Fine/Coarse stays on key 6 across editing pages;
Back/Home remain on keys 1/8. Menu captions use **Curves**; dynamic key captions
use at most two lines of eleven characters, eliding longer recording/curve labels.
Detailed values remain on the touch strip.

The Plus profile has no duplicate Library/navigation keys or Position, Smoothing,
Speed and marker-editor folders. View reset uses the View dial press. Fine/Coarse
is shared by position/marker dials on the same Plus, survives menu changes and
starts in fine mode after plugin startup. Library browsing always steps one entry.

Curve labels follow the application's current view; visibility and availability
follow actual application state. Data mode explicitly shows Raw or Calibrated.

### Plus Selection page

```text
[ Back           ] [               ] [ ] [      ]
[ Zoom selection ] [ Fine / Coarse ] [ ] [ Home ]
Touch: [ Selection Start ] [ Selection End ] [ ] [ ]
Dials: [ Start           ] [ End           ] [ ] [ ]
```

Each notch adjusts only the addressed selection boundary by one/ten source samples.
Start clamps between zero and End; End clamps between Start and the last source
sample. There is no wraparound. Changes take effect immediately through the
existing Inspector selection controls; no preview/apply interaction, replay seek,
marker update, analysis recalculation or Library persistence is involved. Dial
press/touch are unassigned. Fields show confirmed sample/time and the other bound;
GUI edits and recording/target changes publish the current selection. Fine/Coarse
is shared with Position and Markers. Zoom to selection uses the existing view action.

### Neo controls

Use the shared menu hierarchy with keys replacing dial controls. Two native main
pages, Start and Quick controls, make previous/next navigation available through
the left/right Touch Points. No custom Touch Point input handler is installed;
[Elgato](https://www.elgato.com/us/en/p/stream-deck-neo) owns page switching.
The [InfoBar action](https://docs.elgato.com/streamdeck/sdk/guides/neo-infobar/)
is display-only. Native Neo import and physical Touch Point behavior remain open.
Back returns to the parent folder; on Quick controls, Back and Home return to Start.
Start mirrors the Plus App/Library/Explorer/Website row with the same packaged icons.

Quick controls:

```text
[ Back       ] [ Play      ] [ Zoom −      ] [ Zoom + ]
[ Reset view ] [ Zoom Sel. ] [ Reset speed ] [ Home   ]
InfoBar: playback position, state and speed
```

Neo Position and marker editors use center columns for minus/plus, with coarse
steps above fine steps. Smoothing/Speed use keys 6/7 for minus/plus and key 3 for
reset. Explorer/Playback folders form a compact center group; Curves groups the
three force directions above Data mode, Combined and Reset view.

Library page, top and bottom key rows:

```text
[ Back   ] [ Previous ] [ Next ] [ Open ]
[ Import ] [          ] [      ] [ Home ]
InfoBar: selected Library entry
```

Previous/Next use the cyclic selection defined in [Library navigation](#library-navigation).

Marker selection, top and bottom key rows:

```text
[ Back ] [ Start   ] [ Gravity ] [      ]
[      ] [ Incline ] [ End     ] [ Home ]
```

Selecting a marker opens its key editor:

```text
[ Back    ] [ −10 ] [ +10 ] [ Apply ]
[ Discard ] [ −1  ] [ +1  ] [ Home  ]
```

Adjustment keys change only the selected marker's preview. Apply submits that
marker; Discard restores its latest applied value. Use the same source bounds and
persistence contract as the [Plus marker page](#plus-marker-page).
Navigation never implicitly applies a preview.

Contextual InfoBar contents: playback time, play/pause and speed during playback;
selected view for curves; marker name, preview value and pending-change indication
in the marker editor. Marker name/state, current preview/adopted position and last
applied value occupy separate lines. All text fields elide overflow within the
232×50 display. Images use encoded SVG data, shared with key/dial feedback.
The InfoBar remains display-only; disconnects clear program values.

### Plus marker page

The dial order and preview/press interaction are owner-specified.

| Dial, left to right | Marker  | Valid position                                         |
| ------------------- | ------- | ------------------------------------------------------ |
| 1                   | Start   | Source sample zero through the effective End           |
| 2                   | Gravity | Any admitted source sample, independent of ride bounds |
| 3                   | Incline | Any admitted source sample, independent of ride bounds |
| 4                   | End     | Effective Start through the last source sample         |

Prepared physical layout; marker order and dial/touch interaction are confirmed:

```text
[ Back ] [               ] [ ] [ ]
[      ] [ Fine / Coarse ] [ ] [ Home ]
Touch: [ Start + mode ] [ Gravity + mode ] [ Incline + mode ] [ End + mode ]
Dials: [ Start        ] [ Gravity        ] [ Incline        ] [ End        ]
```

Touch fields show sample index and recording time with preview/application status.
Rotate to preview, press to apply, tap the corresponding field to discard.

- Rotation follows the shared [stepping and playback rules](#stepping-and-playback).
- Feedback: marker name, sample index and recording time. Relative replay time changes
  when Start moves; distinguish proposed values from successfully applied values.
- Optional shortcuts: four cursor-position previews and four original-value previews,
  in marker order, across additional pages that preserve Back/Home positions.
- Gravity/Incline may be absent. Initial placement and reset-to-absent behavior
  must follow the existing [marker contract](../implementation/RAW_EXPLORER.md#time-zoom-and-selection).

Rotation changes only the preview, without recalculating analysis or saving to the
Library. Pressing a dial submits only its marker; other dial previews remain
unconfirmed. Tapping its touch field discards only that preview and restores the
latest applied value, without changing other previews or stored markers.
On both devices, preserve previews across menu changes; discard them when the
recording or target Explorer changes. Never apply a preview to another recording/window.
Unset calibration markers are unavailable until set through the GUI; initial
placement through a device remains open.

Use the existing marker service and Library persistence: only an adopted successful
analysis saves the four choices atomically. Concurrent confirmations must not
overwrite other confirmed changes with stale marker state.
Applied Start/End changes currently reset the chart viewport and replay labels;
cursor-following and editing-zoom behavior for this page remain decisions.

## Action scope

Initial implementation:

| Area       | Controls                                                | Possible feedback                  |
| ---------- | ------------------------------------------------------- | ---------------------------------- |
| Playback   | Play/pause; choose existing playback speeds             | Playing/paused; speed              |
| Navigation | Step samples; scrub with a dial                         | Current sample or replay time      |
| View       | Reset view; zoom to selection                           | Action availability                |
| Curves     | Toggle directions, calibrated view and Combined         | Actual visibility and availability |
| Smoothing  | Adjust the existing smoothing window                    | Window size                        |
| Selection  | Adjust inclusive selection Start/End; zoom to it        | Confirmed selection bounds         |
| Markers    | Set ride/calibration markers through existing actions   | Effective marker positions         |

Additional ideas outside the initial scope:

| Area       | Controls                                                | Possible feedback                  |
| ---------- | ------------------------------------------------------- | ---------------------------------- |
| Exports    | Open existing export dialogs; consider preset selection | Availability or export state       |
| Windows    | Choose or switch the controlled Explorer                | Recording/window identity          |

Library browsing, opening in the current window and Import are also included;
their controls are defined in [Library navigation](#library-navigation).

## Integration approach

Use a separate Stream Deck plugin and a local application control interface.
Implement the plugin with the official Elgato TypeScript SDK (`@elgato/streamdeck`)
in the Node.js runtime provided by Stream Deck.
The plugin sends commands and receives actual application state; it does not
simulate keyboard input. The existing file-open transport remains separate.

Loopback WebSocket uses Qt's server and Node's native client. The
[transport contract](../architecture/06_runtime_view.md#stream-deck-transport)
defines discovery, local access and reconnects. Native Windows exchange and recovery
are verified. The [control contract](../architecture/06_runtime_view.md#stream-deck-control-contract)
defines typed commands, responses and feedback. Application dispatch uses existing
GUI actions and analysis services. The SDK key action exposes these commands through
per-key settings and confirmed feedback. Profiles, dials and InfoBar are prepared
with automated checks; physical acceptance remains open.
SDK/tooling versions are fixed in the [workspace manifest](../../plugins/stream-deck/package.json)
and [root npm lockfile](../../package-lock.json); transport and contract use existing dependencies.

The plugin's SDK connection to Stream Deck and its connection to the Analyzer are
separate. No native macOS integration test has been performed.

## Proposed command and feedback behavior

- Address the currently active Explorer explicitly; do not fall back to the first
  open window when no Explorer is active.
- Distinguish successful execution, unavailable action and disconnected application.
- Reject application-control commands while the Analyzer is in the background;
  do not activate it implicitly. Keep state feedback visible and mark controls unavailable.
- Also reject application-control commands during active text/number editing or while
  a dropdown or dialog is open, and show controls as unavailable. Local Stream Deck
  menu navigation remains available.
- Read actual GUI/service state; button presses must not maintain a separate toggle state.
- Include window identity and protocol compatibility; restore current state after reconnect.
- Coalesce playback feedback rather than updating every key for every sample.

### Display capabilities and state

| Surface          | Dynamic feedback                                        | Interaction                               |
| ---------------- | ------------------------------------------------------- | ----------------------------------------- |
| Display keys     | Action icons, on/off state, title or compact value      | Press                                     |
| Plus touch strip | Layout icons, text, values and indicators for each dial | Touch tap; associated dial rotation/press |
| Neo InfoBar      | Layout icons, status text and compact values            | Display only; control through keys        |

- Reuse corresponding application icons where suitable, with distinct active,
  inactive and unavailable appearances. Show availability separately from on/off state;
  reject unavailable commands in the application regardless of the device appearance.
- Drive key toggle states from confirmed application state, disabling automatic SDK
  toggling. Use images/text for additional conditions; key states support two states.
  User-defined key icons/titles take precedence over plugin updates.
- Filled, shaded function icons distinguish import/open, direction, zoom, curves, each marker
  and Apply/Discard. State badges distinguish inactive/active, preview, pending,
  failure, blocked and disconnected conditions by shape and color.
- Plus fields show the selected entry/count, sample/time, confirmed interval/span,
  smoothing window and actual speed/play state. Marker fields retain the last
  applied value separately from preview/pending/failed values. Text is elided to
  field bounds; unknown values remain unavailable. Physical legibility is unverified.
- For markers, distinguish preview, pending application, applied value and failure;
  an unsuccessful confirmation must not appear applied. Clear stale feedback when
  the target closes or the connection is lost.

### Icon assets

Asset sizes and colors follow the [manifest reference](https://docs.elgato.com/streamdeck/sdk/references/manifest/)
and [plugin guidelines](https://docs.elgato.com/guidelines/stream-deck/plugins/).
The sizes below describe SDK assets/layouts, not native LCD resolutions.

| Asset                             | Size in pixels              | Format / color                                 |
| --------------------------------- | --------------------------- | ---------------------------------------------- |
| Key state image                   | 72 × 72; PNG @2x: 144 × 144 | SVG/PNG; full color                            |
| Dial preview in the desktop app   | 72 × 72; PNG @2x: 144 × 144 | SVG/PNG; full color                            |
| Action-list icon                  | 20 × 20; PNG @2x: 40 × 40   | SVG/PNG; white #FFFFFF, transparent background |
| Category icon                     | 28 × 28; PNG @2x: 56 × 56   | SVG/PNG; white #FFFFFF, transparent background |
| Plugin preferences icon           | 256 × 256; @2x: 512 × 512   | PNG                                            |
| Plus touch-field canvas, per dial | 200 × 100                   | JSON layout with image/text items              |
| Neo InfoBar canvas                | 232 × 50                    | JSON layout with image/text items              |

- Bundle assets inside the plugin directory. Manifest image paths omit extensions;
  PNG assets include normal and `@2x` variants. SVG scales without separate raster variants.
- Runtime [key images](https://docs.elgato.com/streamdeck/sdk/guides/keys/#images)
  accept local paths or image data URLs: SVG, PNG, JPEG and WebP. Use SVG or
  high-resolution PNG for our icons. GIF is supported in manifest states, not runtime `setImage`.
- [Layout images](https://docs.elgato.com/streamdeck/sdk/references/layouts/#pixmap)
  use a local path, image data or SVG; their `rect` determines the icon area within
  the canvas. Plus background PNG assets: 200 × 100 and 400 × 200 (`@2x`).
  Plugins cannot draw across the entire Plus touch strip as one canvas.
- Colored device graphics may use transparent PNG/SVG areas. Layout text/backgrounds
  accept named or hexadecimal colors; supported backgrounds/bars also allow gradients.
  Layout item opacity ranges from 0 to 1 in 0.1 steps. No fixed device-icon palette
  is prescribed; the white-only restriction applies to action-list/category icons.
- Vendor examples use 48 × 48 icons in a [Plus layout](https://docs.elgato.com/streamdeck/sdk/guides/dials/)
  and 20 × 20 icons in the [Neo InfoBar](https://docs.elgato.com/streamdeck/sdk/guides/neo-infobar/);
  these are examples, not mandatory icon sizes. Interactive Plus targets must be
  at least 35 × 35 according to the plugin guidelines.

## Open decisions

| Decision             | Choices to discuss                                                                        |
| -------------------- | ----------------------------------------------------------------------------------------- |
| Device coverage      | Additional models; optional Mobile; available Mac hardware and supported macOS baseline   |
| Feedback             | Physical legibility and owner acceptance of icon/layout variants                          |

## Proposed implementation steps

Keys, profiles, dials/touch and InfoBar have local Windows tests and a conditional
CI job. Local installation/startup and profile import are verified. Steps 7–11
remain prepared until physical Plus/Neo acceptance in step 12.

1. **Name:** Agree scope

   - **Status:** Complete.
   - **Content:** Choose actions, target-window rule, feedback and navigation behavior.
   - **Acceptance criteria:** The owner agrees the initial scope, supported devices,
     software compatibility and background/navigation behavior.

2. **Name:** Verify WebSocket transport

   - **Status:** Complete on Windows; native macOS behavior remains unverified.
   - **Content:** Check the Qt server/plugin client, endpoint discovery, local access and reconnects.
   - **Acceptance criteria:** Command/state exchange and reconnects work over loopback
     WebSocket on Windows; record macOS feasibility and any unverified native behavior.
     Platform feasibility and limits are recorded in the
     [runtime transport contract](../architecture/06_runtime_view.md#stream-deck-transport).

3. **Name:** Define control contract

   - **Status:** Complete; typed Python/TypeScript models and shared contract tests.
   - **Content:** Define typed commands, responses, state events and protocol compatibility.
   - **Acceptance criteria:** The contract covers agreed actions, window identity and
     active/available states, displayed values and preview/application status;
     unavailable/disconnected states are explicit. Existing file-open requests remain compatible.
     See the [control contract](../architecture/06_runtime_view.md#stream-deck-control-contract).

4. **Name:** Connect application actions

   - **Status:** Complete on Windows; native macOS behavior remains unverified.
   - **Content:** Route commands on the GUI thread through existing controllers/services.
     Add the **Enable Stream Deck** switch to application settings and persist it
     through the existing user-preference storage; manage the control-server lifecycle.
   - **Acceptance criteria:** Commands affect the designated window and match GUI behavior;
     GUI changes produce matching feedback without separate analysis calculations.
     Switching the active Explorer changes the control target; no active Explorer
     leaves application controls unavailable.
     Marker changes are persisted only after successful analysis adoption.
     Stream Deck is disabled for new users; the preference survives application restarts.
     Enabling starts the control server; disabling disconnects clients, stops the
     server and removes its discovery file. Startup respects the saved preference.

5. **Name:** Add Stream Deck plugin

   - **Status:** Complete on Windows; device-specific and physical acceptance remain in later steps.
   - **Content:** Lock the official TypeScript SDK/tooling versions; implement agreed key
     actions and state feedback.
   - **Acceptance criteria:** The plugin installs locally, executes agreed commands,
     reflects application state through icons and selected titles/values, and handles
     unavailable/restarted applications without reporting unconfirmed toggle changes.

6. **Name:** Add device menus and profiles

   - **Status:** Complete on Windows; native import and SDK key navigation verified.
     Physical device acceptance belongs to step 12.
   - **Content:** Create Plus and Neo profiles with the confirmed menu hierarchy.
   - **Acceptance criteria:** Both profiles provide Library and Explorer menus;
     Back/Home retain their shared positions wherever supported. Plus keys do not
     duplicate its dial functions except for Play/Pause; Neo retains key-only operation.

7. **Name:** Add Library controls

   - **Status:** Prepared.
   - **Content:** Add Plus dial navigation, Neo Previous/Next/Open keys and Import on both devices.
   - **Acceptance criteria:** Selection follows visible sorting/filtering, one entry
     per notch/key press, and wraps both ways, including empty/single-entry handling.
     Browsing never opens entries. Plus dial press or Neo Open opens the selection
     in the current Explorer without a new window; Import opens the existing dialog.
     Device feedback identifies the selected entry and action availability.

8. **Name:** Add Plus navigation controls

   - **Status:** Prepared.
   - **Content:** Add position, view, smoothing and speed dials with touch-field feedback.
   - **Acceptance criteria:** Controls reuse existing application settings and actions;
     position stepping defaults to fine and switches through the Fine/Coarse key.
     Step sizes and playback behavior follow [shared rules](#stepping-and-playback).
     Touch fields show actual state, values and the applicable step mode.

9. **Name:** Add Plus marker controls

   - **Status:** Prepared.
   - **Content:** Add the Start/Gravity/Incline/End dial page and Fine/Coarse key.
   - **Acceptance criteria:** Rotation previews only the intended marker within valid
     sample bounds; press applies it; touch tap discards only its preview and restores
     the latest applied value. Previews survive menu changes and are discarded on
     recording/target-window changes. Touch fields distinguish preview/application status.

10. **Name:** Add Neo marker controls

    - **Status:** Prepared with Windows software checks; native Neo acceptance remains open.
    - **Content:** Add marker selection and the key-based editor from the Neo mockups.
    - **Acceptance criteria:** Start/Gravity/Incline/End selection opens the corresponding
      editor. Separate - coarse / - fine / + fine / + coarse keys adjust its preview;
      Apply submits it and Discard restores the applied value. Bounds, step sizes,
      persistence and preview lifecycle match the Plus marker contract.

11. **Name:** Add Neo InfoBar feedback

    - **Status:** Prepared with Windows software checks; native Neo acceptance remains open.
    - **Content:** Add the agreed contextual icons, status and values to InfoBar layouts.
    - **Acceptance criteria:** Displays follow actual Library, playback, curve and marker
      state, including unavailable data and pending previews. Operation requires no input
      events from the InfoBar.

12. **Name:** Validate and document

    - **Status:** Partial on Windows: automated checks and native Plus installation/connection verified; physical Plus/Neo operation remains open.
    - **Content:** Run affected checks and device tests; align concise usage and architecture docs.
    - **Acceptance criteria:** Relevant Windows and agreed hardware checks pass;
      usage documentation and applicable arc42 decisions match the accepted implementation.
      Claim macOS support only after native application/plugin and device verification.

13. **Name:** Package and release plugin

    - **Status:** Planned.
    - **Content:** Assemble compiled JavaScript, runtime dependencies, manifest, icons,
      layouts and both device profiles. Validate and pack with the official CLI;
      extend the release workflow to attach a separate `.streamDeckPlugin` asset
      alongside the Analyzer packages. Document download, double-click installation
      and selection of the matching device profile.
    - **Acceptance criteria:** One self-contained package installs in Stream Deck 7.6+
      and offers the Plus and Neo profiles. An authorized Analyzer GitHub release
      includes the plugin as its own downloadable asset. Marketplace publication
      remains optional and outside the initial delivery scope.

New ideas update these candidate/decision tables in place; they do not authorize
implementation or enlarge an agreed delivery scope automatically.

## Proposed acceptance

- Selected actions match the GUI and affect only the designated Explorer window.
- Feedback follows both device commands and changes made in the application.
- Verify fixed fine/coarse steps, valid bounds, playback pause/resume rules and command
  rejection during editing, open dropdowns and dialogs.
- Unavailable data, closed windows and reconnects have defined behavior before implementation.
- Verify GUI-originated changes, background-command rejection, multiple windows and application/plugin restarts for the chosen approach.
- Verify agreed key actions on both available devices, dial/touch controls on Plus
  and any chosen custom InfoBar feedback on Neo. Software tests alone do not prove hardware operation.

## Vendor references

- [Qt WebSocket server](https://doc.qt.io/qtforpython-6/PySide6/QtWebSockets/QWebSocketServer.html),
  [Node WebSocket client](https://nodejs.org/api/globals.html#class-websocket),
  [plugin OS declarations](https://docs.elgato.com/streamdeck/sdk/references/manifest/).

- Hardware: [Stream Deck +](https://www.elgato.com/us/en/p/stream-deck-plus),
  [Stream Deck Neo](https://www.elgato.com/us/en/p/stream-deck-neo);
  [Neo InfoBar API and software minimum](https://docs.elgato.com/streamdeck/sdk/guides/neo-infobar/).

- Menu organization: [native folders](https://help.elgato.com/hc/en-us/articles/360027957912-Elgato-Stream-Deck-Using-Folders),
  [profiles with folders and page navigation](https://docs.elgato.com/stream-deck/profiles/getting-started/).

- [Official TypeScript SDK setup](https://docs.elgato.com/streamdeck/sdk/introduction/getting-started/),
  [plugin environment](https://docs.elgato.com/streamdeck/sdk/introduction/plugin-environment/),
  [keys and feedback](https://docs.elgato.com/streamdeck/sdk/guides/keys/),
  [dials](https://docs.elgato.com/streamdeck/sdk/guides/dials/).
- [Devices](https://docs.elgato.com/streamdeck/sdk/guides/devices/),
  [device-specific profiles](https://docs.elgato.com/streamdeck/sdk/guides/profiles/),
  [local plugin distribution](https://docs.elgato.com/streamdeck/sdk/introduction/distribution/).
  [Plugin packaging CLI](https://docs.elgato.com/streamdeck/cli/commands/pack/)
  defines package validation and `.streamDeckPlugin` generation.
