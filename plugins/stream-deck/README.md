# Stream Deck plugin

Key controls using Elgato's TypeScript SDK, enabled for Windows and macOS 15+. The configurable **Analyzer
control** action covers the [agreed commands](../../docs/architecture/06_runtime_view.md#actions).
Plus provides six native pages with a fixed menu; Neo retains Library/Explorer folders.
Plus dials/touch, marker editors and Neo InfoBar are prepared with automated tests.
Native Windows startup, Analyzer connection and import for an attached Plus are
verified. Plus menu/subgroup navigation and swipe feedback are verified on the device;
integrated physical Plus operation is owner-confirmed. Neo operation remains open.

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

## Code style

Elgato's recommended ESLint rules and Prettier configuration apply only within
this workspace. Run from the repository root:

```powershell
npm run lint --workspace plugins/stream-deck
npm run format:check --workspace plugins/stream-deck
```

The Stream Deck CI job runs both checks before building/testing the plugin.
Warnings fail the lint command; formatting differences fail the Prettier check.
Neither check rewrites files.
The local EditorConfig matches Elgato's template, including tabs and a 120-character line
width, with spaces for JSON, Markdown and YAML. Generated `dist/` and `node_modules/`
are excluded. Prettier is configured through this workspace's `package.json`;
the rest of the repository retains its own settings. Development dependencies use
TypeScript 5.9 to satisfy the Elgato configuration's peer requirements.

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
connection in the native logs. Confirm the matching bundled profile when offered;
the manifest requests automatic installation and activation. Manual import is a
fallback if the offer was declined or an older layout remains. Preserve customized
and unrelated user profiles. On a development
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

## Profile and feedback implementation

The [current control contract](../../docs/implementation/STREAM_DECK.md) owns
device menus, keys/dials/touch, bounds, filter proposals and display behavior.
[Runtime architecture](../../docs/architecture/06_runtime_view.md#native-page-routing)
owns page routing, confirmed state and device isolation; the
[deployment view](../../docs/architecture/07_deployment_view.md#mapping-and-environment)
owns bundled-profile identity and installation defaults.

- `scripts/build-profiles.mjs` creates the Plus/Neo/Mobile archives. Plus uses
  six native main pages; Neo folders/Touch Points and Mobile folders use native navigation.
- Navigation/Step size titles and images stay plugin-owned; native custom
  `States[].Image`/`Title` override live feedback. Reimport the updated bundled
  layout if old overrides remain; a plugin restart alone cannot clear them.
- Profile updates replace the bundled `profiles/plus` layout under its existing
  archive identity, preserving customized and unrelated profiles. Native custom
  copies are not SDK page-switch destinations. Request/appearance events are logged.
- `devices/layouts/plus.json` defines five-line fields. The build derives
  `layouts/plus-compact.json` for four-line fields; no second source layout is maintained.
- The build crops canonical `devices/backgrounds/*.svg` into sixteen 200×100
  `layouts/backgrounds/` tiles. Dial settings carry menu/column; display-only
  Library dial 2 renders its tile and ignores every gesture. Subgroups share artwork.
- `scripts/render_stream_deck_reference.py` renders actual profiles/layouts and
  production feedback, including native-size state/lock examples. It does not
  establish hardware qualification; settings and optical axes belong to the
  [presentation contract](../../docs/implementation/STREAM_DECK.md#state-feedback-and-locks).
- Application protocol 3 carries selection bounds, Library filters and the
  `library.open.same` / `library.open.new` commands;
  discovery/authentication stays at 1. Update/restart both components together.
  The key-settings editor does not expose filter-set commands.
- Neo uses the shared icons/two-line captions. Its InfoBar has no input handlers;
  native Touch Points change pages independently of application feedback.
- `profiles/mobile.streamDeckProfile` targets SDK device type 3 with six keys,
  no dials/InfoBar and no Home action. Pairing remains in Stream Deck; the Analyzer
  endpoint stays desktop loopback. Layout orientation is a user setting, not a
  profile lock; no separate portrait profile or phone-facing service exists.

## Configure keys

1. Enable **Settings → Application → Enable Stream Deck** in Analyzer.
2. Drag **Ride Forces Analyzer → Analyzer control** onto a key.
3. Choose the command and applicable direction, sample step, curve or marker.
4. Keep the intended Explorer active. Input fields, dialogs and background use block commands.

Create separate marker Preview, Apply and Discard keys. Preview steps are ±1/±10/±20
source samples. Library browsing selects one visible entry cyclically; Open opens
the selection in the current Explorer. Generic key bindings are available on Plus
and Neo; native qualification limits are recorded in
[validation](../../docs/validation/STREAM_DECK.md).

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
is recorded in [validation](../../docs/validation/STREAM_DECK.md#open-native-checks).
