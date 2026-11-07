# Stream Deck plugin

Key controls using Elgato's TypeScript SDK, enabled for Windows and macOS 15+. The configurable **Analyzer
control** action covers the [agreed commands](../../docs/architecture/06_runtime_view.md#actions).
Plus provides six native pages with a fixed menu; Neo retains Library/Explorer folders.
Plus dials/touch, marker editors and Neo InfoBar are prepared with automated tests.
Native Windows startup, Analyzer connection and import for an attached Plus are
verified. Plus menu/subgroup navigation and swipe feedback are verified on the device;
complete physical Plus acceptance and Neo operation remain open.

For everyday operation, see the [Stream Deck + user guide](../../docs/user/STREAM_DECK.md)
with illustrated functions and state explanations.

## Independent plugin version

The plugin has its own version, independent of the Analyzer application and control
protocol. `plugins/stream-deck/package.json` is authoritative; the source/built
Elgato manifests use the same version with a fourth `.0` component. For example,
package `0.2.0` becomes Elgato `0.2.0.0`.

Keep one upcoming plugin version throughout development, including multiple
commits and builds. After a release, increment it once when preparing the next
changed plugin, from the repository root:

```powershell
npm version patch --workspace plugins/stream-deck --no-git-tag-version
npm run check:version --workspace plugins/stream-deck
```

Use `minor` or `major` instead for the corresponding change. The npm lifecycle
hook synchronizes the manifest; npm maintains the workspace lock metadata. This
command creates no Git commit or tag. Repeated builds do not change versions.

Every build checks manifest/lock consistency. Version progression compares code/data
against the preceding reachable app release tag (`vMAJOR.MINOR.PATCH`, including
the app's alpha/beta/release-candidate suffixes), rather than individual commits.
Changed source assets, device/profile/build definitions, shared Node inputs or the
license require a version higher than at that release. Further development commits
can reuse that upcoming version. Documentation/tests alone and app-only releases
need no bump. Before the first release containing the plugin, no earlier plugin
version is imposed. Clean tagged release builds compare against the preceding tag;
tagging HEAD cannot conceal an omitted increase. Full Git history and release tags
are required; no GitHub request or additional plugin tag is needed.

## Local build and installation

Use the repository's [Windows setup](../../docs/development/SETUP.md). From the repository root:

```powershell
npm run test:stream-deck
```

Tests compile TypeScript, bundle the plugin, run official offline validation and
exercise the built process against local simulated SDK/app WebSocket hosts. The
suite then runs its Python/Qt reference-image check through `npm run test:reference`.
Use the locked repository Python environment and uv alongside Node for that check;
no Analyzer window or application implementation is loaded by the image generator.
These tests require no
Stream Deck software or hardware. VS Code's Node test provider performs the same
build before running selected Node tests. The Python reference check is separate
from application/UI discovery. [CI selection](../../docs/development/CI.md#routing-and-required-gate)
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
It does not need repository `node_modules` at runtime. Builds also create `profiles/plus.streamDeckProfile` and
`profiles/neo.streamDeckProfile` and `profiles/mobile.streamDeckProfile` inside that folder.
All three profiles use the SDK defaults: `Readonly: false`, `AutoInstall: true`,
`DontAutoSwitchWhenInstalled: false`. Stream Deck offers the matching profile during
plugin installation and switches to it after installation. Manual archive import
is a fallback, not the normal setup path. Unrelated user profiles are preserved.
Neo/Mobile menu images are embedded per page. Plus menu and Step size images and
captions come from live plugin feedback; its profile must not set custom Image/Title overrides.
Replace an older Plus profile to remove those overrides; restarting the plugin
alone cannot clear them from an installed profile.

## Installable archive

From the repository root, build and pack with the official Elgato CLI:

```powershell
npm run pack:plugin --workspace plugins/stream-deck
```

The command builds, validates offline and writes
`.tmp/stream-deck-package/Ride-Forces-Analyzer.streamDeckPlugin`.
The official CLI's output is renamed; the internal plugin ID and `.sdPlugin`
folder name remain unchanged.
It includes the self-contained runtime, icons/layouts, license notices and all three
profiles. It neither installs the plugin nor changes existing profiles. An existing
archive is preserved by default; append `-- --force` only to replace it deliberately.
The archive version comes from the independent plugin version, not the app version.
After tests have already built the artifact, `npm run pack:built-plugin --workspace
plugins/stream-deck` packs that tested folder without rebuilding. Release CI uses
this path and retains the archive with `PLUGIN-SHA256SUMS.txt`; the publication job
verifies both before attaching them to the authorized release.

For native installation, double-click the archive with Stream Deck installed and
confirm its installation prompt. Verify the installed version and actual SDK/app
connection in the native logs, then import the matching bundled profile separately;
profiles are not auto-installed. Keep existing user profiles. On a development
machine, the linked plugin already occupies the same plugin ID: retain that setup
until a deliberate switch to archive installation is intended.

Archive contents and byte integrity are checked automatically on Windows. Native
archive installation/update and macOS execution remain unverified. The file is a
prepared GitHub release asset; uploading/publishing it requires separate owner
authorization. The existing tag-release workflow handles that upload after its
quality/checksum gates. No Marketplace publication is configured.

## macOS: enabled, unverified

The manifest allows macOS 15+, matching the Analyzer distribution target, and
uses the same `bin/plugin.js` and bundled dependencies as Windows. No Windows
native binary is required by the installed plugin. Stream Deck 7.6+ supplies its
Node.js runtime. Native macOS installation/startup, connection, foreground/focus
handling and device operation have not been verified.

The existing local build/link/restart commands above use Node and Elgato's CLI;
`start.ps1` and other Windows application setup scripts are not Mac launchers.
Use the Mac Analyzer `.app` and enable Stream Deck in its settings. On Neo/Mobile,
select that `.app` in the native Start app action; Plus starts directly on Library. Discovery uses
`~/Library/Application Support/Ride Forces Analyzer/stream-deck.json` on both sides.
No custom launcher or platform-specific plugin bundle is added. Profile import
and native app/website actions on macOS remain unverified.

## Device menus

Plus starts on Library and has six native main pages in order: Library,
Playback / Navigate, Playback / Selection, Curves, Markers / Markers and Markers / View.
Keys 1–4 always select Library, Playback, Curves and Markers. Keys 6/7 select
Navigate/Selection or Markers/View in their corresponding groups; key 8 carries
Step size. Playback and Marker groups recall the last subgroup confirmed on that
device during the plugin session. Cyan marks the group/page confirmed by
`willAppear`, including native swipes; sending a request never confirms selection.
Plus has no Back, Home, Start app or Website assignments. Library keys 5–8 are Open,
New window, Import and Reset filters; Curves keys 5–8 are the three force slots and
Raw/Calibrated. Playback and Markers have Play/Pause on key 5. Main menu captions
show confirmed Library selection/count, playback state, data mode and marker state
(Failed before Pending before preview count), independent of the visible page.

Navigation requests target the manifest profile `profiles/plus`, not an arbitrary
imported user copy. The six-page layout replaces the former Plus layout under the
same profile identity and archive filename; no parallel Plus profile is bundled.
The bundled profile is offered during plugin installation and activated after
installation. Existing Plus installations receive the replacement layout under
the same identity; unrelated profiles are preserved. Copies are not navigation destinations. Native Windows import, SDK page switching, subgroup recall and physical swipe
feedback are verified on Plus. A sent SDK request alone is not proof of success. Request/appearance events are recorded in plugin logs.

Neo retains Start → Library / Explorer, its folders, native Start app/Website,
Back on key 1 and Home on key 8. Its Open action uses the packaged app icon and an
installation-specific EXE/shortcut or Mac `.app`; Website uses the project URL.
Mobile retains its reduced Start/Library/Playback/View folders. Both are unchanged.
Menu navigation works without an Analyzer connection. Dynamic captions remain
short; detailed application values stay on the touch strip.

The Library dial selects one visible entry per notch, cyclic in both directions; press
opens the selection in the current Explorer. Library dial 2 is unassigned;
dials 3/4 choose Park/Status options in application dropdown order without wrapping.
Rotation changes a device-local proposal only; press sends `library.filter.set`,
touch requests All for that field. Feedback separates the proposal from Active;
only received state confirms a change. Reset filters discards both local proposals
before sending the existing reset command. GUI/option changes discard that field's
proposal; leaving Library, target/recording/session changes and connection loss
discard affected proposals. Locks block filter gestures; no proposal/command is replayed.
Playback/Navigate and Markers/View dials are
Position (press: Play/Pause), Speed (1×), Zoom (Reset) and press-only Zoom selection.
Playback/Selection replaces the first two with Selection Start/End.
Curves has Smoothing, press-only Combined, Zoom (Reset) and Position (press: Play/Pause).
Press-only controls ignore rotation and touch, even while unavailable.
Smoothing stops at 1/51 samples without wrapping; press resets
to 11. Raw mode retains unfiltered source values and disables smoothing.
Markers are Start/Gravity/Incline/End: rotate previews, press applies and touch
discards only that marker's preview. Step size on Playback/Markers pages cycles
through 1/10/20/1 source samples per notch on that Plus; startup defaults to 1.
The key and touch fields show Fine (1), Medium (10) or Coarse (20), shared across
these pages. The matching icons use one, two or three bars.

Plus Selection dials adjust the current inclusive selection directly through the
Inspector controls. Bounds clamp at zero, each other and the last source sample;
there is no wraparound, marker adoption or Library marker write. Their touch fields
show actual start/end values. Press/touch are unassigned on these two dials.
Application protocol version 4 carries these bounds and Library filter choices/commands; update/restart
Analyzer and the plugin together. Discovery/authentication stays at version 1.
`library.filter.set` selects Park or Status by its exact dropdown value; snapshots
include ordered values/labels and the confirmed selection. Null is All, an empty
park is Unknown park. User text stays unchanged Unicode within the existing 64 KiB
message limit. Filter dials use exact values, including null for All and the empty
park string for Unknown; the key-settings editor does not expose filter-set commands.
`library.filter.reset` clears Park, Status and search. Existing profile settings
using `library.reset_filters` map to this command; the wire protocol uses only the
canonical name.

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

## Limited Mobile preview

`profiles/mobile.streamDeckProfile` targets SDK device type 3 with a six-key
2×3 layout. It provides Start, Library, Playback and View using only existing key
actions and the shared icons/captions. Back is key 1; no Home action is assigned.
Playback uses key 6 for Reset view, View for Play/Pause. No dial, InfoBar, marker,
curve/smoothing/speed or manual selection-boundary editors are included.

Pair Mobile in Stream Deck, select its six-key layout and import onto that device.
The Library landscape rows are Back/Previous/Next and Import/Open/New window.
Recommend the Mobile layout-orientation setting None or Fixed for a stable 3×2
grid. Orientation is configured by the user, not enforced by the profile.
Native Back stays on key 1 at the top left.
All three Library profiles offer New window, using the existing archived-recording
window action. Plus puts it on key 6 beside Open; Neo on key 7 beside Open;
Mobile on key 6 beside Open. Already open/loading recordings activate their existing
Explorer instead of opening another. Normal Open/dial press uses the current
Explorer for recordings not already open elsewhere.
Start app retains a user-configured desktop EXE/shortcut path; Website is preset.
The Analyzer transport stays on desktop loopback. No mobile-facing endpoint or
new application commands are introduced. Full Mobile hardware acceptance remains
open. [Instructions and small preview](../../docs/user/STREAM_DECK.md#mobile-limited-six-key-preview)
are rendered by the same screenshot script as Plus/Neo.

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

The manifest enables Windows and macOS 15+ using the same JavaScript bundle.
macOS installation, application/plugin/device behavior and hardware acceptance
remain unverified. Physical device acceptance
belongs to the [remaining integration steps](../../docs/requirements/STREAM_DECK.md#implementation-steps).
