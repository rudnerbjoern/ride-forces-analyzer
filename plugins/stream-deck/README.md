# Stream Deck plugin

Windows key controls using Elgato's TypeScript SDK. The configurable **Analyzer
control** action covers the [agreed commands](../../docs/architecture/06_runtime_view.md#actions).
Plus and Neo profiles provide native Library/Explorer menus and key controls.
Plus dials/touch, marker editors and Neo InfoBar remain planned.

## Local build and installation

Use the repository's [Windows setup](../../docs/development/SETUP.md). From the repository root:

```powershell
npm run test:stream-deck
npm run link:plugin --workspace plugins/stream-deck
npm run restart:plugin --workspace plugins/stream-deck
```

Tests compile TypeScript, bundle the plugin, run official offline validation and
exercise the built process against local SDK/app WebSocket hosts. They require no
Stream Deck software or hardware. VS Code's Node test provider performs the same
build before running selected tests. [CI selection](../../docs/development/CI.md#routing-and-required-gate)
runs plugin tests for affected changes and always for releases/full CI.

For a build without tests, use `npm run build:plugin --workspace plugins/stream-deck`.
`validate:plugin` runs the official CLI with `--no-update-check`.

Local installation requires Stream Deck 7.6+. The CLI links
`io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin` into Stream Deck's plugin
directory. The stable reverse-DNS ID derives from the project's GitHub Pages address.
The folder contains manifest, icons and inspector sources; ignored build output
adds self-contained JavaScript, the project license and bundled-runtime notices.
It does not need repository `node_modules` at runtime. A release `.streamDeckPlugin`
asset remains planned. Builds also create `profiles/plus.streamDeckProfile` and
`profiles/neo.streamDeckProfile` inside that folder; double-click the matching
archive to import it into Stream Deck. Existing user profiles are preserved.

## Device menus

Both profiles provide Start → Library / Explorer → Playback / View / Curves / Markers.
Native folders handle navigation; Home returns to Start on the invoking device,
including when Analyzer is disconnected. Back stays on key 1 and Home on key 8
in every submenu. Stream Deck fixes native folder Back at key 1 during import;
the preferred key 5 placement is unsupported. Start has no Back/Home keys.

Library includes Previous/Next/Open/Import keys. Playback provides Play/Pause and
Position, Smoothing and Speed folders with existing key actions; Position includes
fine/coarse steps and zoom. View / Curves contains the five curve/mode controls and
Reset view. Marker folders reserve Start/Gravity/Incline/End in order; editor
bindings belong to their later integration steps. No dial or InfoBar is required
to navigate the menus or use the assigned controls.

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
- Active/inactive, unavailable, pending, failed and disconnected states have
  distinct vector icons. Automatic key-state toggling is disabled; a press or
  acknowledgement alone never changes the displayed toggle value.
- Settings persist per key through Stream Deck. User-defined key icons/titles
  take precedence over plugin updates.
- Disconnection clears actionable state and pending requests. Reconnect requires
  a fresh snapshot; commands are never replayed. Invalid/incompatible protocol
  messages disable control. See the [wire contract](../../docs/architecture/06_runtime_view.md#stream-deck-control-contract).

The manifest currently targets Windows. macOS discovery is prepared but native
application/plugin/device behavior is unverified. Physical device acceptance
belongs to the [remaining integration steps](../../docs/requirements/STREAM_DECK.md#proposed-implementation-steps).
