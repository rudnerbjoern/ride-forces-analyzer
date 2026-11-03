# Stream Deck integration

<!-- cspell:words Elgato streamdeck -->

## Current status

- Implemented: local transport, application routing, versioned plugin, Plus/Neo
  profiles and limited Mobile preview, keys, Plus dials/touch and Neo InfoBar.
- Verified on Windows: automated application/plugin checks, official plugin
  validation, native plugin startup/Analyzer connection and Plus profile import.
- Open: physical Plus operation, native Neo/Mobile import and operation, and all
  native macOS integration checks.
- Distribution: self-contained development folder, three profile archives and an
  officially packed `.streamDeckPlugin`. Native archive installation and release
  publication remain open.

## Scope and constraints

- Optional control of the current Analyzer Explorer; application processing stays
  offline and independent of Stream Deck. Original recordings remain read-only.
- Reuse existing GUI/service actions, validation, analysis and Library persistence.
  No keyboard simulation, separate force calculations or phone-facing Analyzer service.
- Stream Deck 7.6+ with the official TypeScript SDK and Stream Deck's Node.js runtime.
  Dependencies are locked in the [workspace manifest](../../plugins/stream-deck/package.json)
  and [npm lockfile](../../package-lock.json).
- Manifest platforms: Windows and macOS 15+. Both use the same JavaScript bundle;
  macOS installation, connection, focus handling and device operation are unverified.
- **Enable Stream Deck** defaults to off. Save persists/applies the setting; Cancel
  leaves it unchanged. Startup respects it; disable/shutdown stops the server and
  removes its owned discovery file.
- Plugin versioning is independent of the application and control protocol.
  Development commits share one upcoming version. Changed code/packaged data require
  an increase over the preceding release tag; builds also check package/manifest/lock
  consistency. Documentation/tests alone and app-only releases need no increase.
  See the [version workflow](../../plugins/stream-deck/README.md#independent-plugin-version).
- Export controls, an explicit target-window selector and other device models are
  outside this implementation. Marketplace publication is outside current delivery.

## Model support

| Device             | Prepared controls                          | Native acceptance                                 |
| ------------------ | ------------------------------------------ | ------------------------------------------------- |
| Stream Deck +      | 2×4 keys, four push dials, touch strip     | Windows import verified; physical operation open  |
| Stream Deck Neo    | 2×4 keys, InfoBar, two native Touch Points | Import and physical operation open                |
| Stream Deck Mobile | Reduced 2×3 key preview                    | Import, pairing and phone operation open          |

[User guide](../user/STREAM_DECK.md) and [profile illustrations](../images/README.md)
show the generated assignments. Images are software examples, not hardware evidence.

## Integration and command contract

- Separate connections: plugin ↔ Stream Deck SDK; plugin ↔ Analyzer loopback WebSocket.
- Discovery/authentication version 1; application protocol version 2. Strict typed
  messages identify the target window, recording and generation. Incompatible or
  stale-target commands are rejected rather than redirected.
- Use the active Explorer; never select an arbitrary window or activate Analyzer
  implicitly. Block application commands during background operation, text/number
  editing, open dropdowns/dialogs, missing data or conflicting analysis.
- Native folders, Home, app/website actions and local Fine/Coarse remain independent
  of Analyzer command availability.
- Feedback follows confirmed GUI/service state. A press or transport acknowledgement
  must not imply that a toggle changed or marker analysis was adopted.
- Disconnect clears actionable/pending state; reconnect requires a fresh snapshot.
  Never queue/replay disconnected commands. Preserve the separate file-open transport.
- Coalesce playback feedback and reuse existing analysis services.

Detailed ownership and wire contracts remain in
[building blocks](../architecture/05_building_block_view.md),
[transport](../architecture/06_runtime_view.md#stream-deck-transport) and
[control contract](../architecture/06_runtime_view.md#stream-deck-control-contract).

## Device controls

### Menu structure

- Plus/Neo Start: native Start app, Library, Explorer and Website actions.
- Plus Explorer: Playback, Curves, Markers and Selection.
- Neo Explorer: Playback, Curves and Markers. Playback adds Position, Smoothing
  and Speed folders; Markers opens the four individual key editors.
- Neo native main pages: Start and Quick controls. Its Touch Points select the
  previous/next native page; the InfoBar action receives no input events.
- Mobile Start: Start app, Library, Playback and Website. Playback opens View.
- Back is key 1 in every folder. Plus/Neo Home is key 8 and returns the invoking
  device to Start. Neo Quick controls uses Start-return actions for Back/Home.
  Mobile deliberately has no Home key.
- Number keys left to right, top row first. Menu changes never apply a marker
  preview or switch the target Explorer.
- Start app uses Elgato Open with the packaged app icon and a user-configured
  desktop EXE/shortcut or Mac `.app`. Website uses Elgato Website, the project URL
  and the bundled globe icon. Neither action requires an Analyzer connection.

### Library navigation

- Plus dial 1: one visible entry per notch; press opens it. Neo/Mobile use
  Previous, Next and Open keys. Import opens the existing file-import dialog.
- Follow visible sorting/filtering and skip hidden entries. Wrap in both
  directions; a single entry stays selected, an empty list cannot be opened.
- Rotation/browsing changes selection only. Open uses the current Explorer and
  never creates another window.
- Library stepping always uses one entry, independent of Fine/Coarse.
- Keys show short action names and selected index/count. Plus touch/Neo InfoBar
  show the selected name; full names remain available in the Analyzer Library.

### Stepping and playback

- Plus Fine/Coarse is per device, defaults to fine after plugin startup and survives
  menu changes. Key 6 switches Position, Selection and marker dials between 1/10
  source samples per notch. Library is unaffected.
- Neo Position/marker editors expose fixed −10/+10 and −1/+1 keys. Mobile exposes
  only −1/+1 position steps.
- Position, Selection and marker adjustments clamp to valid bounds; only Library
  navigation wraps. Display sample index and existing replay-time labels.
- Manual position changes and marker previews pause playback. Apply/Discard do not
  resume it. Play resumes it; view/curve/selection/speed changes leave it running.
- Smoothing moves through existing odd windows 1–51, stops at both ends and resets
  to 11. Raw mode retains unfiltered source values and disables smoothing.
- Speed uses existing playback settings; reset returns to 1×. Zoom/reset reuse
  existing chart navigation.

### Plus profile

Back/Home occupy keys 1/8 in submenus. Blank positions are unassigned. No duplicate
keys/editors for dial functions, except the dedicated Play/Pause key.

| Page      | Other assigned keys                          | Dials, left to right                  |
| --------- | -------------------------------------------- | ------------------------------------- |
| Start     | 1 App; 2 Library; 3 Explorer; 4 Website      | None                                  |
| Library   | 5 Import                                     | 1 Browse/Open                         |
| Explorer  | 2 Playback; 3 Curves; 6 Markers; 7 Selection | None                                  |
| Playback  | 5 Play/Pause; 6 Fine/Coarse                  | 1 Position; 2 View; 3 Speed; 4 unused |
| Curves    | 2/3/4 directions; 5 Data mode; 7 Combined    | 1 Smoothing                           |
| Selection | 5 Zoom to selection; 6 Fine/Coarse           | 1 Selection Start; 2 Selection End    |
| Markers   | 6 Fine/Coarse                                | 1 Start; 2 Gravity; 3 Incline; 4 End  |

Position press toggles playback; View press resets the view; Speed press resets
to 1×; Smoothing press resets to 11. Selection press/touch are unassigned.
Marker press/touch follow the [marker contract](#plus-marker-page).

### Selection bounds

- Adjust the inclusive Inspector Select range immediately, independently of ride
  Start/End markers. Start clamps between zero and End; End between Start and the
  last source sample. No wraparound or preview/apply phase.
- GUI changes and recording/target changes publish current bounds.
- No replay seek, pause, analysis recalculation or Library marker write. Existing
  selection-based views/exports use the same GUI range.

### Plus marker page

| Dial | Marker  | Admitted samples                                      |
| ---- | ------- | ----------------------------------------------------- |
| 1    | Start   | Zero through effective End                            |
| 2    | Gravity | Any valid source sample, independent of ride bounds   |
| 3    | Incline | Any valid source sample, independent of ride bounds   |
| 4    | End     | Effective Start through last source sample            |

- Rotate: preview only that marker. Press: apply only its preview. Touch: discard
  only its preview and restore the applied value. Other previews remain untouched.
- Preserve previews across menus; discard them on recording/target changes.
  Never apply a preview to a different recording/window.
- Only successful analysis adoption atomically persists current Library marker
  choices. Concurrent confirmations must not overwrite newer adopted state.
- Show preview/pending/failed values separately from the last applied value.
  Unsuccessful or interrupted adoption must not appear applied.
- Unset calibration references require initial placement through the GUI. There
  is no device action for initial placement or resetting markers to source values.
- Applied Start/End changes use existing viewport/replay-label behavior. Follow the
  [Explorer marker contract](../implementation/RAW_EXPLORER.md#time-zoom-and-selection).

### Neo profile

Back/Home occupy keys 1/8 in submenus. Start matches Plus; Quick controls is a
second native main page. No dials or custom Touch Point command handlers.

| Page                  | Other assigned keys                                                 |
| --------------------- | ------------------------------------------------------------------- |
| Quick controls        | 2 Play; 3/4 Zoom −/+; 5 Reset view; 6 Zoom selection; 7 Reset speed |
| Library               | 2 Previous; 3 Next; 4 Open; 5 Import                                |
| Explorer              | 2 Playback; 3 Curves; 6 Markers                                     |
| Playback              | 2 Play; 3 Smoothing; 6 Position; 7 Speed                            |
| Position              | 2/3 −10/+10; 6/7 −1/+1                                              |
| Smoothing / Speed     | 3 Reset; 6/7 −/+                                                    |
| Curves                | 2/3/4 directions; 5 Data mode; 6 Combined; 7 Reset view             |
| Markers               | 2 Start; 3 Gravity; 6 Incline; 7 End                                |
| Individual marker     | 2/3 −10/+10; 4 Apply; 5 Discard; 6/7 −1/+1                          |

Marker editors use the same bounds, preview lifecycle and persistence as Plus.
InfoBar feedback is contextual: Library name/index, playback position/state/speed,
curve visibility, smoothing or markers. A marker editor separates name/state,
preview/adopted position and last applied value across three lines. Disconnect
clears program values; native paging remains separate from feedback.

### Limited Mobile preview

Four six-key pages, three columns and two rows; no Home, dials or InfoBar.
Back is key 1 in folders. Pairing is handled by Stream Deck; the Analyzer keeps
its existing desktop loopback interface. Mobile import/phone operation are unverified.

| Page     | Key 1     | Key 2    | Key 3    | Key 4      | Key 5          | Key 6      |
| -------- | --------- | -------- | -------- | ---------- | -------------- | ---------- |
| Start    | Start app | Library  | Playback | Website    | Unassigned     | Unassigned |
| Library  | Back      | Previous | Next     | Open       | Import         | Unassigned |
| Playback | Back      | Play     | View     | −1 sample  | +1 sample      | Reset view |
| View     | Back      | Zoom −   | Zoom +   | Reset view | Zoom selection | Play       |

No curve/smoothing/speed editors, markers or manual selection-boundary editing.

## Feedback and assets

- Use shared filled/color function artwork and separate badges for inactive,
  active, preview, pending, failed, unavailable and disconnected states.
- Drive toggles from confirmed snapshots; disable automatic key-state toggling.
  Honor native user icon/title overrides. Encode runtime SVG image data.
- Key captions: at most two lines of eleven characters. Use action labels rather
  than recording names on Library keys. Elide long variable labels within bounds.
- Plus fields retain actual values/mode, selected name/count, viewport span,
  smoothing or speed. Marker fields retain adopted values beside proposed state.
- Neo InfoBar is display-only. All text fields elide overflow; unavailable values
  and disconnected state must not show fabricated/current-looking data.
- Assets are bundled; runtime operation requires no image download. White-only
  graphics apply to action-list/category icons, not device displays.

| Asset                     | Contract                                        |
| ------------------------- | ----------------------------------------------- |
| Key / dial preview        | SVG or PNG 72×72 and 144×144                    |
| Action-list / category    | White transparent SVG/PNG; 20×20 / 28×28        |
| Plugin preferences        | PNG 256×256 and 512×512                         |
| Plus field / Neo InfoBar  | JSON layouts bounded to 200×100 / 232×50        |

[Generated profiles](../../plugins/stream-deck/scripts/build-profiles.mjs),
[feedback](../../plugins/stream-deck/src/feedback.ts) and
[layouts](../../plugins/stream-deck/devices/layouts) define the current device data.

## Implementation steps

**Implemented** means code and automated Windows checks exist; it does not imply
physical device or macOS acceptance. **Partial** identifies outstanding delivery
or acceptance work. Native acceptance is tracked explicitly in steps 6 and 12.

1. **Agree scope**
   - **Status:** Complete.
   - **Acceptance:** Devices, actions, target rule and foreground behavior are defined above.

2. **Verify WebSocket transport**
   - **Status:** Implemented; Windows transport acceptance verified.
   - **Acceptance:** Authenticated Qt/Node exchange, limits, access checks and reconnects;
     native macOS exchange remains open.

3. **Define control contract**
   - **Status:** Implemented; shared Python/TypeScript contract checks pass.
   - **Acceptance:** Explicit targets, strict versions/shapes, request results and full
     state snapshots; file-open requests remain independent.

4. **Connect application actions**
   - **Status:** Implemented; automated Windows application acceptance verified.
   - **Acceptance:** Existing GUI/service routing, focus/dialog/background locks,
     target changes, marker adoption/persistence and saved server opt-in lifecycle.

5. **Add Stream Deck plugin**
   - **Status:** Implemented; Windows build, official validation and SDK-host checks pass.
   - **Acceptance:** Bundled runtime, confirmed key feedback, recovery without replay,
     independent version enforcement; macOS is enabled but native checks remain open.

6. **Add device menus and profiles**
   - **Status:** Implemented; native Plus import verified.
   - **Acceptance:** Plus/Neo/Mobile layouts, fixed Back/Home rules, native launch/website
     actions and Neo main pages; native Neo/Mobile import remains open.

7. **Add Library controls**
   - **Status:** Implemented; automated Windows application/SDK checks pass.
   - **Acceptance:** Visible order/filtering, one-entry cyclic stepping, empty/single-entry
     cases, explicit current-window Open, Import and confirmed feedback. Device checks remain open.

8. **Add navigation controls**
   - **Status:** Implemented; automated Windows application/SDK checks pass.
   - **Acceptance:** Plus position/view/speed/smoothing and independent Selection bounds;
     Neo key alternatives and reduced Mobile navigation, clamping, mode and playback rules.

9. **Add Plus marker controls**
   - **Status:** Implemented; automated Windows application/SDK checks pass.
   - **Acceptance:** Start/Gravity/Incline/End order, per-marker preview/apply/discard,
     bounds, lifecycle and adopted-value feedback. Physical dial/touch checks remain open.

10. **Add Neo marker controls**
    - **Status:** Implemented; automated Windows key-handler/profile checks pass.
    - **Acceptance:** Four editors, coarse/fine pairs, Apply/Discard and shared marker
      rules. Native Neo import and physical operation remain open.

11. **Add Neo InfoBar feedback**
    - **Status:** Implemented; automated Windows SDK-host/layout checks pass.
    - **Acceptance:** Contextual confirmed values, separate marker state/adopted value,
      overflow and disconnect handling, no input handlers. Native Neo display checks remain open.

12. **Validate and document**
    - **Status:** Partial.
    - **Verified:** Automated Windows checks, native plugin startup/connection and Plus
      profile import; requirements, user guide and generated profile illustrations exist.
      Windows developer mode is enabled; native SDK logs and the installed plugin's
      established connection to the current Analyzer endpoint confirm its running state.
    - **Open:** Physical Plus keys/dials/touch, Neo import/keys/Touch Points/InfoBar,
      Mobile import/pairing/phone operation, and native macOS integration.
      Available access is Windows remote control without physical device input.
      See the [native acceptance checklist](#native-acceptance-checklist).

13. **Package and release plugin**
    - **Status:** Partial.
    - **Implemented:** Self-contained `.sdPlugin` folder, three bundled profile archives,
      license notices, official offline validation/packing and archive-content checks;
      local link/restart workflow. The [pack command](../../plugins/stream-deck/README.md#installable-archive)
      prepares the `.streamDeckPlugin` release asset without installing or publishing it.
      Release CI retains the tested archive and checksum; the publication job verifies
      and attaches both. Hosted execution/publication has not been verified for this change.
    - **Open:** Native archive-install/update acceptance and separately authorized
      publication of the GitHub release asset.
      Marketplace publication is not part of this step.

## Acceptance gates

- Windows software checks must cover GUI parity, target changes, state feedback,
  locks, fixed stepping/clamping, persistence, analysis adoption and recovery.
- Native logs must confirm SDK startup and Analyzer connection; CLI success alone
  is insufficient. Software preview/configuration clicks are not physical-input evidence.
- Hardware acceptance requires actual observation or user confirmation for each
  device/input type. Software illustrations and SDK mocks cannot establish it.
- Native macOS installation, connection, focus handling and device behavior require
  execution on macOS before verified support can be claimed.
- Public delivery requires a validated installable archive and explicit release
  authorization. Existing user profiles/settings must survive installation/updates;
  changed profile layouts require separate import.

### Native acceptance checklist

Each row requires actual observation or user confirmation on the named device.
The Windows automated checks cover the corresponding software contracts; they
do not close these rows. Preserve existing profiles and original recordings.

| Device / area                    | Required observation                                                                                                                                                                                    | Status |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| Plus menus / keys                | Navigate Start, Library, Explorer and submenus; Back is key 1, Home key 8; Play/Pause and key alternatives work.                                                                                        | Open   |
| Plus Library                     | Dial follows visible order/filtering, wraps both ways and handles empty/single-entry lists; rotation only selects, press opens in the current Explorer; Import opens the existing dialog.               | Open   |
| Plus navigation / selection      | Position, zoom, speed and smoothing presses work; Fine/Coarse starts at 1 and switches to 10 samples; Library stays at one entry; smoothing and selection bounds clamp.                                 | Open   |
| Plus markers                     | Start/Gravity/Incline/End rotate to preview, press to apply and touch to discard independently; bounds and adoption feedback are correct; menus preserve previews, recording/target changes clear them. | Open   |
| Plus feedback / locks / recovery | GUI changes reach the device; text focus, dialogs and background operation block app commands; disconnect/reconnect and Explorer changes clear stale state without replay or false confirmation.        | Open   |
| Neo                              | Import on an actual Neo; verify folder keys/editors, both native Touch Points and contextual InfoBar values, marker states, overflow and disconnected display.                                          | Open   |
| Mobile                           | Pair the phone, select six keys and import on Mobile; verify all four pages, Back without Home, commands, confirmed feedback and reconnection.                                                          | Open   |
| macOS                            | Install/start natively; verify discovery/authentication, app connection, focus/dialog/background locks, recovery and operation of each device claimed as verified.                                      | Open   |

## References

- [User guide](../user/STREAM_DECK.md), [plugin build/install/version workflow](../../plugins/stream-deck/README.md).
- [Transport and control architecture](../architecture/06_runtime_view.md#stream-deck-control-contract).
- [Elgato SDK manifest](https://docs.elgato.com/streamdeck/sdk/references/manifest/),
  [keys](https://docs.elgato.com/streamdeck/sdk/guides/keys/),
  [dials](https://docs.elgato.com/streamdeck/sdk/guides/dials/),
  [Neo InfoBar](https://docs.elgato.com/streamdeck/sdk/guides/neo-infobar/).
- [Native folders](https://help.elgato.com/hc/en-us/articles/360027957912-Elgato-Stream-Deck-Using-Folders),
  [profiles](https://docs.elgato.com/stream-deck/profiles/getting-started/),
  [plugin packaging](https://docs.elgato.com/streamdeck/cli/commands/pack/).
