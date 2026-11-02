# Stream Deck integration

<!-- cspell:words Elgato streamdeck -->

Status: Initial scope agreed; SDK bootstrap and local test scaffold present.
Analyzer controls, transport and device features remain planned.

## Confirmed scope

- Windows first, with Stream Deck + and Neo available for development and testing.
- Minimum Stream Deck software version: 7.6.
- macOS compatibility where feasible; support remains unverified until native checks pass.
- Integration: separate plugin and local control interface; no hotkey simulation.
- Plugin: official Elgato TypeScript SDK (`@elgato/streamdeck`), using Stream Deck's Node.js runtime.
- Preferred transport: loopback WebSocket with the same protocol on Windows and macOS.
- Stream Deck + and Neo use the [menu hierarchy](#menu-structure) below.
- Application control is foreground-only; no operation while another application has focus.
- The currently active Explorer is the control target; no active Explorer means
  application controls are unavailable.
- Library controls browse existing entries and explicitly open the selected entry.
- Requested Plus marker-page order, left to right: Start, Gravity, Incline, End.
- Marker interaction: turn to preview, press to apply, tap the touch field to discard its preview.
- Provide dynamic icons, activation/availability feedback and useful state or values
  on keys, the Plus touch strip and Neo InfoBar where supported.
- The [initial action scope](#action-scope) is confirmed.
- Distribution: one `.streamDeckPlugin` asset on Analyzer GitHub releases, with
  device-specific Plus and Neo profiles.
- Implemented scope is limited to the SDK bootstrap and local test scaffold.

## Goal and constraints

Optional Library and Explorer control from Stream Deck, with application-state feedback where useful.

- Application processing remains offline and independent of Stream Deck.
- Commands reuse existing actions, validation and analysis services.
- Original recordings remain read-only; no separate force calculations in the plugin.
- Development follows the existing [platform constraints](../architecture/02_architecture_constraints.md).

## Existing basis

Playback, sample stepping, zoom, curve visibility and smoothing already have
application controls.
The [local instance transport](../architecture/06_runtime_view.md#qt-bootstrap)
currently accepts file-open requests, not general control or status subscriptions.
It acknowledges each request and closes the connection; continuous feedback needs
a new contract. Keyboard stepping is suppressed during playback or while an input
field has focus; device controls follow the [stepping and playback rules](#stepping-and-playback).

## Model support

| Available device                         | Controls                                                     | Planning role                                          |
| ---------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------ |
| Stream Deck +                            | Eight keys, four push dials and touch strip                  | Primary development and dial/touch testing             |
| Stream Deck Neo                          | Eight keys, InfoBar and two Touch Points for page navigation | Key-only operation, pages and optional InfoBar testing |

Use shared logical key actions with device-specific profiles. Dial functions need
key alternatives; other models remain possible but unverified. Simultaneous use
of both devices is an open choice, not a prerequisite.

Neo InfoBar actions are display-only and receive no input events. Custom feedback
requires SDK 3.
Keep the normal page navigation separate from plugin status displays.

## Device controls

The shared menu hierarchy, Library navigation, marker interactions and Neo layout
below are confirmed; other assignments remain proposals.

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
    └── Markers
        └── Start · Gravity · Incline · End
```

Keep Back at bottom-left (key 5) and Home at bottom-right (key 8) on both devices
where supported, across menus, editors and additional pages. Number keys left to
right, top row first. Leave these positions unassigned on Start. Verify placement
with the chosen profile/folder navigation before finalizing device layouts.

Use bundled device-specific profiles with native nested folders and pages,
rather than a custom menu engine. Profiles can include the agreed key, dial and
display assignments. Plugin-driven navigation can switch bundled profiles and
pages; it cannot switch to arbitrary user-created profiles. Exact layout and
Plus dial assignments per menu remain open and require hardware verification.
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
| Smoothing | Adjust the existing odd sample window | Reset smoothing        | Window size                 |
| Playback  | Select an existing playback speed     | Return to normal speed | Actual speed and play state |

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

Proposed physical placement of confirmed actions and candidate controls, following
the shared Back/Home positions. Each page
has two key rows, followed by four touch fields and four dials where assigned.
Blank positions are unassigned; menu-only pages leave touch fields/dials unassigned.
Labels represent icons with short titles or values; final artwork remains open.

Start:

```text
[ Library ] [ Explorer ] [ ] [ ]
[         ] [          ] [ ] [ ]
```

Library:

```text
[ Import ] [ ] [ ] [      ]
[ Back   ] [ ] [ ] [ Home ]
Touch: [ Selected entry ] [ ] [ ] [ ]
Dials: [ Browse / Open  ] [ ] [ ] [ ]
```

The first Library dial rotates through entries cyclically and opens on press.

Explorer:

```text
[ Playback ] [ View / Curves ] [ Markers ] [      ]
[ Back     ] [               ] [         ] [ Home ]
```

Playback, using the candidate assignments in [Navigation page](#navigation-page):

```text
[ Play / Pause ] [ ] [ ] [      ]
[ Back         ] [ Fine / Coarse ] [ ] [ Home ]
Touch: [ Time/sample + mode ] [ View interval ] [ Window size ] [ Speed/state ]
Dials: [ Position           ] [ View          ] [ Smoothing   ] [ Speed       ]
```

View / Curves, candidate controls:

```text
[ Curve 1 ] [ Curve 2    ] [ Curve 3  ] [ Reset view ]
[ Back    ] [ Calibrated ] [ Combined ] [ Home       ]
```

Curve labels follow the application's current view; visibility and availability
follow actual application state. Dial assignments for this page remain open.

### Neo controls

Use the shared menu hierarchy with keys replacing dial controls. Touch Points
switch additional pages within a section; Back returns to the parent menu.

Library page, top and bottom key rows:

```text
[ Previous ] [ Next ] [ Open ] [ Import ]
[ Back     ] [      ] [      ] [ Home   ]
InfoBar: selected Library entry
```

Previous/Next use the cyclic selection defined in [Library navigation](#library-navigation).

Marker selection, top and bottom key rows:

```text
[ Start ] [ Gravity ] [ Incline ] [ End  ]
[ Back  ] [         ] [         ] [ Home ]
```

Selecting a marker opens its editor:

```text
[ - coarse ] [ - fine  ] [ + fine ] [ + coarse ]
[ Back     ] [ Discard ] [ Apply  ] [ Home     ]
```

Adjustment keys change only the selected marker's preview. Apply submits that
marker; Discard restores its latest applied value. Use the same source bounds and
persistence contract as the [Plus marker page](#plus-marker-page).
Navigation never implicitly applies a preview.

Contextual InfoBar contents: playback time, play/pause and speed during playback;
selected view for curves; marker name, preview value and pending-change indication
in the marker editor. The InfoBar remains display-only.

### Plus marker page

The dial order and preview/press interaction are owner-specified.

| Dial, left to right | Marker  | Valid position                                         |
| ------------------- | ------- | ------------------------------------------------------ |
| 1                   | Start   | Source sample zero through the effective End           |
| 2                   | Gravity | Any admitted source sample, independent of ride bounds |
| 3                   | Incline | Any admitted source sample, independent of ride bounds |
| 4                   | End     | Effective Start through the last source sample         |

Proposed physical layout; marker order and dial/touch interaction are confirmed:

```text
[      ] [ ] [ ] [      ]
[ Back ] [ Fine / Coarse ] [ ] [ Home ]
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
Initial positions for unset markers remain open.

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
| Markers    | Set ride/calibration markers through existing actions   | Effective marker positions         |

Additional ideas outside the initial scope:

| Area       | Controls                                                | Possible feedback                  |
| ---------- | ------------------------------------------------------- | ---------------------------------- |
| Selection  | Set selection start/end at the current sample           | Selection bounds                   |
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

Loopback WebSocket is the preferred transport for Windows and macOS. A candidate
is Qt's WebSocket server in the Analyzer and a WebSocket client in the plugin.
Endpoint discovery, local access, protocol compatibility and reconnects still need
verification. SDK/tooling versions are fixed in the [workspace manifest](../../plugins/stream-deck/package.json)
and [root npm lockfile](../../package-lock.json); additional transport dependencies remain undecided.

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
- Show relevant existing values with units or a clear unavailable indication.
  Candidate contents are listed with the actions and device pages above; exact
  contents and layouts remain open.
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
| Feedback             | Final icon variants and layout details per surface                                        |

## Proposed implementation steps

Device integration remains planned; the SDK bootstrap has local tests and a conditional CI job.

1. **Name:** Agree scope

   - **Status:** Complete.
   - **Content:** Choose actions, target-window rule, feedback and navigation behavior.
   - **Acceptance criteria:** The owner agrees the initial scope, supported devices,
     software compatibility and background/navigation behavior.

2. **Name:** Verify WebSocket transport

   - **Status:** Planned.
   - **Content:** Check the Qt server/plugin client, endpoint discovery, local access and reconnects.
   - **Acceptance criteria:** Command/state exchange and reconnects work over loopback
     WebSocket on Windows; record macOS feasibility and any unverified native behavior.

3. **Name:** Define control contract

   - **Status:** Planned.
   - **Content:** Define typed commands, responses, state events and protocol compatibility.
   - **Acceptance criteria:** The contract covers agreed actions, window identity and
     active/available states, displayed values and preview/application status;
     unavailable/disconnected states are explicit. Existing file-open requests remain compatible.

4. **Name:** Connect application actions

   - **Status:** Planned.
   - **Content:** Route commands on the GUI thread through existing controllers/services.
   - **Acceptance criteria:** Commands affect the designated window and match GUI behavior;
     GUI changes produce matching feedback without separate analysis calculations.
     Switching the active Explorer changes the control target; no active Explorer
     leaves application controls unavailable.
     Marker changes are persisted only after successful analysis adoption.

5. **Name:** Add Stream Deck plugin

   - **Status:** In progress; SDK bootstrap and local/CI test scaffold only.
   - **Content:** Lock the official TypeScript SDK/tooling versions; implement agreed key
     actions and state feedback.
   - **Acceptance criteria:** The plugin installs locally, executes agreed commands,
     reflects application state through icons and selected titles/values, and handles
     unavailable/restarted applications without reporting unconfirmed toggle changes.

6. **Name:** Add device menus and profiles

   - **Status:** Planned.
   - **Content:** Create Plus and Neo profiles with the confirmed menu hierarchy.
   - **Acceptance criteria:** Both profiles provide Library and Explorer menus;
     Back/Home retain their shared positions wherever supported. Key-only operation
     remains possible; unselected features stay out of scope.

7. **Name:** Add Library controls

   - **Status:** Planned.
   - **Content:** Add Plus dial navigation, Neo Previous/Next/Open keys and Import on both devices.
   - **Acceptance criteria:** Selection follows visible sorting/filtering, one entry
     per notch/key press, and wraps both ways, including empty/single-entry handling.
     Browsing never opens entries. Plus dial press or Neo Open opens the selection
     in the current Explorer without a new window; Import opens the existing dialog.
     Device feedback identifies the selected entry and action availability.

8. **Name:** Add Plus navigation controls

   - **Status:** Planned.
   - **Content:** Add position, view, smoothing and speed dials with touch-field feedback.
   - **Acceptance criteria:** Controls reuse existing application settings and actions;
     position stepping defaults to fine and switches through the Fine/Coarse key.
     Step sizes and playback behavior follow [shared rules](#stepping-and-playback).
     Touch fields show actual state, values and the applicable step mode.

9. **Name:** Add Plus marker controls

   - **Status:** Planned.
   - **Content:** Add the Start/Gravity/Incline/End dial page and Fine/Coarse key.
   - **Acceptance criteria:** Rotation previews only the intended marker within valid
     sample bounds; press applies it; touch tap discards only its preview and restores
     the latest applied value. Previews survive menu changes and are discarded on
     recording/target-window changes. Touch fields distinguish preview/application status.

10. **Name:** Add Neo marker controls

    - **Status:** Planned.
    - **Content:** Add marker selection and the key-based editor from the Neo mockups.
    - **Acceptance criteria:** Start/Gravity/Incline/End selection opens the corresponding
      editor. Separate - coarse / - fine / + fine / + coarse keys adjust its preview;
      Apply submits it and Discard restores the applied value. Bounds, step sizes,
      persistence and preview lifecycle match the Plus marker contract.

11. **Name:** Add Neo InfoBar feedback

    - **Status:** Planned.
    - **Content:** Add the agreed contextual icons, status and values to InfoBar layouts.
    - **Acceptance criteria:** Displays follow actual Library, playback, curve and marker
      state, including unavailable data and pending previews. Operation requires no input
      events from the InfoBar.

12. **Name:** Validate and document

    - **Status:** Planned.
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
