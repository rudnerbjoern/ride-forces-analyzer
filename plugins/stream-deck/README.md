# Stream Deck plugin

Windows key controls using Elgato's TypeScript SDK. The configurable **Analyzer
control** action covers the [agreed commands](../../docs/architecture/06_runtime_view.md#actions).
Plus and Neo profiles provide native Library/Explorer menus and key controls.
Plus dials/touch, marker editors and Neo InfoBar are prepared with automated tests.
Native Windows startup, Analyzer connection and import for an attached Plus are
verified; physical Plus/Neo operation remains open.

For everyday operation, see the [Stream Deck + user guide](../../docs/user/STREAM_DECK.md)
with illustrated functions and state explanations.

## Local build and installation

Use the repository's [Windows setup](../../docs/development/SETUP.md). From the repository root:

```powershell
npm run test:stream-deck
```

Tests compile TypeScript, bundle the plugin, run official offline validation and
exercise the built process against local SDK/app WebSocket hosts. They require no
Stream Deck software or hardware. VS Code's Node test provider performs the same
build before running selected tests. [CI selection](../../docs/development/CI.md#routing-and-required-gate)
runs plugin tests for affected changes and always for releases/full CI.

For a build without tests, use `npm run build:plugin --workspace plugins/stream-deck`.
`validate:plugin` runs the official CLI with `--no-update-check`.

Builds write `.tmp/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/`
from the source assets and `devices/` definitions. Tests neither install/link/restart
the plugin nor import profiles. This also preserves an existing source-folder installation.

Enable developer mode first with `npm exec --workspace plugins/stream-deck -- streamdeck dev`.
Optional local installation requires Stream Deck 7.6+.
`npm run link:plugin --workspace plugins/stream-deck` copies the prepared artifact
to `.tmp/stream-deck-installed/` and links that independent copy using the official CLI.
Use `npm run restart:plugin --workspace plugins/stream-deck` to load it.
An older source/build-folder link must first be removed with
`npm exec --workspace plugins/stream-deck -- streamdeck unlink io.github.rudnerbjoern.ride-forces-analyzer`.
Confirm startup in the native/plugin logs; CLI success alone does not confirm a running plugin.
The stable reverse-DNS ID derives from the project's GitHub Pages address.
The assembled folder contains metadata, layouts, icons, inspector,
self-contained JavaScript, the project license and bundled-runtime notices.
It does not need repository `node_modules` at runtime. A release `.streamDeckPlugin`
asset remains planned. Builds also create `profiles/plus.streamDeckProfile` and
`profiles/neo.streamDeckProfile` inside that folder; double-click the matching
archive to import it into Stream Deck. Existing user profiles are preserved.
Native menu images are embedded per page from the same colored artwork as the
function keys. Reimport an updated profile to refresh its menu images; a plugin
restart alone cannot replace images already stored in an imported profile.

## Device menus

Both profiles provide Start → Library / Explorer → Playback / View / Curves / Markers.
Both Start pages add native Elgato Open and Website actions around Library/Explorer.
Open reuses the packaged app icon; its path is intentionally empty until the user
selects the Analyzer EXE or a Windows shortcut in Stream Deck. Discovery has no
executable path. Website opens the project URL from this plugin's manifest. These
actions require no Analyzer connection or additional plugin command.
Plus labels the view folder Curves and also provides Selection with Start/End dials,
Fine/Coarse and Zoom to selection. Its Explorer folders form a central 2×2 group.
Native folders handle navigation; Home returns to Start on the invoking device,
including when Analyzer is disconnected. Import, Play and selection Zoom use key 5
above the related dials; Data mode sits above Smoothing. Fine/Coarse stays on key 6.
Dynamic captions have at most two short lines; full values remain on the touch strip. Back stays on key 1 and Home on key 8
in every submenu. Stream Deck fixes native folder Back at key 1 during import;
the preferred key 5 placement is unsupported. Start has no Back/Home keys.

Plus keys provide menus, Import, Play/Pause, Zoom to selection, Fine/Coarse and the five curve/mode controls.
Play/Pause is available both as a key and on the Position dial press. Other keys
do not duplicate Library browsing/opening, navigation, view reset
or marker functions assigned to dials. There are no additional Plus Position,
Smoothing, Speed or marker-editor folders. Neo retains Previous/Next/Open/Import,
playback/navigation keys and marker-key editors.

Plus Library dial: one visible entry per notch, cyclic in both directions; press
opens the selection in the current Explorer. Playback dials are Position
(press: Play/Pause), View (Reset) and Speed (1×) in adjacent slots 1–3; slot 4 is unused.
View / Curves has the Smoothing dial in its first slot beside the force-line and
Raw/Calibrated keys. Smoothing stops at 1/51 samples without wrapping; press resets
to 11. Raw mode retains unfiltered source values and disables smoothing.
Markers are Start/Gravity/Incline/End: rotate previews, press applies and touch
discards only that marker's preview. Fine/Coarse on Playback and Markers switches
between one/ten source samples per notch on that Plus, including Selection; startup defaults to fine.

Plus Selection dials adjust the current inclusive selection directly through the
Inspector controls. Bounds clamp at zero, each other and the last source sample;
there is no wraparound, marker adoption or Library marker write. Their touch fields
show actual start/end values. Press/touch are unassigned on these two dials.
Application protocol version 2 carries these bounds and commands; update/restart
Analyzer and the plugin together. Discovery/authentication stays at version 1.

Plus touch fields show selected entry/count, sample/time, actual view interval/span,
odd smoothing window and playback speed/state. Marker fields keep the proposed
value separate from the last applied value, including pending/failed adoption.
Long field text is elided. The display-only Neo InfoBar also shows confirmed values, availability,
preview/pending/failed status and applied marker values. Previews survive menus;
the application clears them on recording/target changes. Unset calibration markers
remain unavailable until placed in the GUI. Input fields/dialogs/background use
block app commands; local menus and fine/coarse selection remain available.

## Neo preparation

Neo retains key alternatives and uses the same icons/two-line captions as Plus.
Native Touch Points select between Start and Quick controls; the latter provides
Play/Pause, Zoom −/+, Reset view, Zoom to selection and Reset speed. Back/Home
return to Start there. Folders keep the normal parent Back and Home assignments.
Position/marker minus and plus occupy the two center columns, coarse above fine;
marker Apply is key 4, Discard key 5. Smoothing/Speed use keys 6/7 and Reset on 3.
The InfoBar displays current Library/playback/view state; marker name/state,
preview/adopted position and last applied value use separate lines. Overflow is
elided, SVG icons are encoded, and the InfoBar has no input handlers.

[Neo controls and example image](../../docs/user/STREAM_DECK.md#neo-keys-infobar-and-touch-points)
are generated by the same script as Plus, directly from the built profile and
production feedback. Neo is not connected: native import and hardware acceptance
remain open. Do not import its profile onto the connected Plus for acceptance.

## Configure keys

1. Enable **Settings → Application → Enable Stream Deck** in Analyzer.
2. Drag **Ride Forces Analyzer → Analyzer control** onto a key.
3. Choose the command and applicable direction, sample step, curve or marker.
4. Keep the intended Explorer active. Input fields, dialogs and background use block commands.

Create separate marker Preview, Apply and Discard keys. Preview steps are ±1/±10
source samples. Library browsing selects one visible entry cyclically; Open opens
the selection in the current Explorer. Generic key bindings are available on Plus
and Neo; physical device acceptance remains open.

## Feedback and connection

- Keys show confirmed playback/curve state, selected Library entry, position,
  smoothing, speed and marker values. Preview, pending and failed marker states
  remain distinct from adopted values.
- Filled, shaded vector illustrations distinguish browsing, opening/importing, sample
  direction, zoom, curves, individual markers and Apply/Discard. State badges use
  different shapes and colors for active/inactive, preview, unavailable, pending,
  failed and disconnected states. Automatic key-state toggling is disabled; a press or
  acknowledgement alone never changes the displayed toggle value.
- Settings persist per key through Stream Deck. User-defined key icons/titles
  take precedence over plugin updates.
- Disconnection clears actionable state and pending requests. Reconnect requires
  a fresh snapshot; commands are never replayed. Invalid/incompatible protocol
  messages disable control. See the [wire contract](../../docs/architecture/06_runtime_view.md#stream-deck-control-contract).

The manifest currently targets Windows. macOS discovery is prepared but native
application/plugin/device behavior is unverified. Physical device acceptance
belongs to the [remaining integration steps](../../docs/requirements/STREAM_DECK.md#proposed-implementation-steps).
