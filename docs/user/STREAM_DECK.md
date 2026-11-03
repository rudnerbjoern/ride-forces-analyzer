# Control Analyzer with Stream Deck +, Neo and Mobile

Use the plugin to browse your Library, control playback and view settings, and
prepare or apply recording markers. Controls act on the Analyzer
window you are currently using; they do not open another window.

The Plus and Neo profiles use the same colored icons and short key captions.
The examples use the English plugin labels. The Analyzer can use its own selected
interface language. Physical Plus operation, Neo/Mobile import and operation,
plugin installation/update and macOS operation remain unverified.
Requires Stream Deck **7.6+**;
the plugin runs on the desktop, alongside Analyzer.

## Set up the controls

1. Obtain `Ride-Forces-Analyzer.streamDeckPlugin` and
   `PLUGIN-SHA256SUMS.txt` from the same [GitHub release](https://github.com/rudnerbjoern/ride-forces-analyzer/releases)
   and compare the archive SHA-256 with the checksum file
   (`Get-FileHash` on Windows, `shasum -a 256` on macOS), then double-click the
   archive and confirm Stream Deck's installation prompt.
2. Import the matching bundled profile as described below and select the correct
   connected device in Stream Deck's import dialog.
   Existing profiles remain available.
   To receive updated menu pictures and button assignments, import the updated
   profile as well. Keep your customized profile if you want to preserve its layout.
3. In Analyzer, enable **Settings → Application → Enable Stream Deck** and save.
4. Select **Ride Forces Analyzer +** or **Ride Forces Analyzer Neo** in Stream Deck. On Start, select **Start app**
   in the software preview and choose your Analyzer EXE or a Windows shortcut in
   **Open** action's file field. The bundled profile leaves this path
   empty because it depends on your installation.
5. Bring the intended Analyzer Explorer to the foreground and click the chart.

### Find and import the device profile

Profiles are included in the plugin but are **not imported automatically**. In
Stream Deck, open **Preferences → Profiles**, select the target device and use
**Import** to open the corresponding archive:

| Device            | Profile file               | Profile name                        |
| ----------------- | -------------------------- | ----------------------------------- |
| Plus              | `plus.streamDeckProfile`   | Ride Forces Analyzer +              |
| Neo               | `neo.streamDeckProfile`    | Ride Forces Analyzer Neo            |
| Mobile (six keys) | `mobile.streamDeckProfile` | Ride Forces Analyzer Mobile Preview |

The files are in the installed plugin's `profiles` subfolder:

- Windows: `%APPDATA%\Elgato\StreamDeck\Plugins\io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin\profiles`
- macOS: `~/Library/Application Support/com.elgato.StreamDeck/Plugins/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/profiles`

Pair Mobile with the desktop Stream Deck app before importing its profile.
Do not replace unrelated profiles or import a Neo/Mobile profile onto Plus.

Operate the **physical LCD keys, dials and touch strip**. Clicking a key in the
Stream Deck desktop application's preview selects its configuration; it does not
execute that key. Keep Analyzer in the foreground when using application controls.

## macOS availability

The plugin requires **macOS 15+** with **Stream Deck 7.6+**. Mac installation
and operation are **unverified**.
Use the Mac Analyzer `.app` and set **Start app** to that `.app` in Stream Deck;
the Windows EXE/shortcut instructions above apply only to Windows.

## Update or troubleshoot the connection

Plugin and Analyzer versions are independent. Install the plugin archive supplied
with the intended Analyzer release; the application update checker does not update
the plugin. GitHub installation does not register Marketplace updates. Install a
new archive manually and reimport its profile only when you want its changed
assignments or menu graphics. Keep your customized profiles.

If controls stay offline, check that Analyzer is running, **Enable Stream Deck**
was saved, and the app/plugin came from a compatible release. There is no manual
port field. If a lock badge appears, close open dialogs/dropdowns, leave text
fields and bring the intended Explorer forward. The plugin's menus still work without a connection.
Clicking the desktop preview only edits a key; actual device input is required
to execute it. See [locks and connection changes](#understand-locks-and-connection-changes).

## Recognize the functions and states

![Stream Deck Plus software illustration of all seven profile pages, two rows of four keys, aligned touch-strip fields and four dials](../images/stream-deck-plus-controls.png)

*Software illustration of all seven Plus profile pages with keys, touch strip
and four dials. Values and marker states are examples.
[Open the full-size image](../images/stream-deck-plus-controls.png).*

The colored illustration identifies the function. A separate badge indicates its
current state; a dimmed icon can still show the last confirmed value.

| Badge / state            | Meaning                                                           |
| ------------------------ | ----------------------------------------------------------------- |
| Neutral dot              | Ready, or a toggle currently off. Check the displayed value.      |
| Green check              | Active toggle or a confirmed applied marker.                      |
| Purple pencil            | Marker preview; the proposed value has not been applied.          |
| Blue clock               | A change is being processed. Wait for confirmation.               |
| Red cross                | A change failed; the previous applied value is kept.              |
| Amber lock               | Control unavailable; the text gives the reason.                   |
| Gray disconnected symbol | No connection. Values disappear until it reconnects.              |

The display follows confirmed program state, including changes you make with
the mouse in Analyzer. Wait for the displayed state to change after pressing a key.

## Move through the menus

**Start** offers **Start app**, **Library**, **Explorer** and **Website** from left
to right. **Start app** opens the application you selected during setup; **Website** opens
the [project website](https://rudnerbjoern.github.io/ride-forces-analyzer/) in your
browser. Both work without an Analyzer connection. Explorer contains **Playback**,
**Curves** and **Markers** in a central group. Plus also has **Selection**.

In each Plus/Neo submenu, **Back** is key **1** (top-left) and **Home** is key **8**
(bottom-right). Home returns to Start. Keys are numbered left to right, top row
first. Start has no Back or Home key. On **Plus**, Fine/Coarse stays on key **6**
on Playback, Selection and Markers. Key captions use two short lines; detailed values remain
on the touch strip. Menu navigation remains available while
Analyzer is disconnected or application commands are blocked.

## Browse and open Library recordings

These dial instructions are for **Plus**. See the separate [Neo](#neo-keys-infobar-and-touch-points)
and [Mobile](#mobile-limited-six-key-preview) sections for their buttons.

Open **Library**. Turn the **first dial** to select one visible recording per
notch. It follows the Library's current sorting and filters and wraps in either
direction. One recording stays selected; an empty list cannot be opened.

Turning only selects. **Press the dial** to open the selection in the current
Explorer. The Plus profile has no additional Previous/Next/Open keys.
**Import** opens Analyzer's existing recording-import dialog; choose files there
with the mouse or keyboard. The touch field shows the selected name and its
position in the visible list. Import is key **5**, directly above the Library dial.

## Control playback and the view

Open **Explorer → Playback**. Dials 1, 2 and 3 (left to right) are assigned;
dial 4 is unused:

| Dial         | Turn                                             | Press         | Touch-strip information                               |
| ------------ | ------------------------------------------------ | ------------- | ----------------------------------------------------- |
| 1 · Position | Move through samples; stop at the ends.          | Play/pause.   | Sample, replay time, play state and Fine/Coarse mode. |
| 2 · View     | Zoom the time axis.                              | Reset view.   | Actual visible interval and its duration in seconds.  |
| 3 · Speed    | Select the next supported playback speed.        | Return to 1×. | Actual speed and play/pause state.                    |

**Fine / Coarse** switches Position, Selection and marker dials between **1** and
**10 samples per notch**. It starts in Fine mode, survives menu changes and never
changes Library stepping.

Position changes pause playback. Zoom, curves, smoothing and speed changes leave
playback running. Use Play to resume after a manual position or marker adjustment.

Position, Smoothing and Speed have no additional key folders on Plus. The
**Play/Pause** key **5**, directly above Position, and the Position dial press both toggle playback.
**Reset view** is the View dial press.

## Curves, Raw/Calibrated and smoothing

Open **Explorer → Curves**. The three force-line keys turn the corresponding
lines on/off. **Data mode** shows and switches between **Raw** and **Calibrated**;
**Combined** controls the combined curve. Data mode is key **5**, above the
Smoothing dial; the three direction keys are grouped across the top row. Labels
and on/off states follow Analyzer.

The **first dial** selects the smoothing window: **1, 3, …, 51 samples**. Further
turns below 1 stay at 1; turns above 51 stay at 51. There is no wraparound in either
direction. Press the dial to reset smoothing to **11 samples**.

Raw mode displays unfiltered source values and disables smoothing, matching the
Analyzer's Inspector. The touch field shows **Raw source values**; select
**Calibrated** before adjusting smoothing.

## Adjust the selection and zoom to it

Open **Explorer → Selection**. Dial **1** adjusts the selection's **Start** sample;
dial **2** adjusts its **End** sample. The touch fields show the confirmed sample
and time, the opposite boundary and Fine/Coarse mode. **Fine / Coarse** switches
between **1** and **10 samples per notch**, shared with Position and Markers.

Turns apply directly to the current Select range, just like the Inspector's
**From sample / To sample** fields. Start stops at zero or End; End stops at Start
or the last source sample. Further outward turns stay at the boundary, without
wrapping. Dial presses and touch taps are unassigned on this page.

Press **Zoom / Selection** on key **5** to fit the chart to that range. Selection changes made in Analyzer
also appear on the touch strip. These controls do not move the replay cursor or
change the recording's markers or calibration.

## Preview, apply or discard markers

Open **Explorer → Markers**. Dial order is **Start, Gravity, Incline, End**.

1. **Turn** a dial to change only that marker's preview. This pauses playback;
   the chart calculations and saved markers stay unchanged.
2. Check the sample/time and the **Preview** status. The separate **Applied** line
   shows the value currently in use.
3. **Press** that dial to apply its preview. **Pending** means the chart is still
   updating. **Applied** confirms success; **Failed** retains the previous value.
4. **Tap the corresponding touch field** to discard only its preview.

Start cannot pass End, and End cannot pass Start. Gravity and Incline may lie
outside Start/End but must remain inside the source recording. If either reference
is unset, place it in Analyzer first.

Previews survive menu changes. Opening another recording or changing the target
Explorer clears them. Applying or discarding one marker does not confirm the
others and does not resume playback. Applied markers are saved automatically
for that Library recording.

The Plus Markers page has Back, Home and Fine/Coarse keys alongside its four
dials. It has no additional marker-key editors.

## Neo keys, InfoBar and Touch Points

Neo uses the eight keys instead of dials. Import `neo.streamDeckProfile` when a
Neo is connected. Its Start row is **Start app · Library · Explorer · Website**;
configure the app path once, as described above. The Plus profile is separate.

![Stream Deck Neo software illustration of all fourteen prepared pages, two rows of four keys, contextual InfoBar values and the two native Touch Points](../images/stream-deck-neo-controls.png)

*Software illustration of the Neo profile. Values are examples;
device operation remains unverified. [Open full size](../images/stream-deck-neo-controls.png).*

The **left/right Touch Points** are native previous/next-page controls. The
profile provides two main pages: **Start** and **Quick controls**. Quick controls
contains Play/Pause, Zoom −/+, Reset view, Zoom to selection and Reset speed.
The InfoBar displays information; use the Touch Points beside it to switch pages.

Folders stay reachable from Start. Back is key **1**, Home is key **8**; on Quick
controls both return to Start. In Position and each marker editor, the two center
columns are **minus / plus**. The top pair uses **10 samples** and the bottom
pair **1 sample**. Marker **Apply** is key **4**, **Discard** key **5**. Preview,
apply and discard retain the same recording/target rules as Plus.

Smoothing and Speed put **−/+** on keys **6/7** and **Reset** on key **3**.
Library offers Previous/Next, Open and Import. Curves groups three direction
keys above Data mode, Combined and Reset view.

The InfoBar follows confirmed program state: selected Library entry and index,
position/time and playback speed, curve visibility, smoothing or marker state.
Marker name/state is on the first line, the preview or applied position on
the second, and the last applied value on the third. Long text is elided within
the display; disconnected state clears program values.

## Mobile: limited six-key preview

The prepared **Ride Forces Analyzer Mobile Preview** profile uses **two rows of
three buttons**. Pair Stream Deck Mobile with the Stream Deck desktop app, choose
its six-key layout and import `mobile.streamDeckProfile` onto that Mobile device.
The plugin still requires Stream Deck 7.6 or later and **Enable Stream Deck** in
Analyzer. [Elgato's setup instructions](https://help.elgato.com/hc/en-us/articles/16786832942221-Elgato-Stream-Deck-Mobile-2-0-Getting-Started)
cover pairing with the desktop Stream Deck app.

![Stream Deck Mobile limited preview showing the four actual six-key pages Start, Library, Playback and View, with Back and no Home button](../images/stream-deck-mobile-controls.png)

*Software illustration of the Mobile profile with example values.
Mobile import, pairing and actual phone operation remain unverified.*

- **Start:** Start app, Library, Playback and Website. Configure the Analyzer EXE or
  Windows shortcut (or the Mac `.app`) on the **desktop** in Start app's Open settings.
- **Library:** Previous/Next, Open and Import. Browsing follows visible sorting and
  filters; only Open opens the selection in the current Explorer. Keys show short
  action names and the selected index/count; the full recording name stays in
  the Analyzer Library (and on the Plus touch strip or Neo InfoBar).
- **Playback:** Play/Pause, one sample backward/forward, Reset view and the View folder.
- **View:** Zoom −/+, Reset view, Zoom to selection and Play/Pause.

**Back is key 1; there is no Home key.** Key 6 is used for Reset view on Playback
and Play/Pause on View. Library keeps one key free for your own assignment.
This preview omits curve/smoothing/speed editors, markers and manual selection
bounds. Use the Analyzer window for those controls. Mobile buttons follow the same
connection and locking rules as the other devices.

## Understand locks and connection changes

Controls are blocked while another application is in front, an Analyzer text/number
field or dropdown is selected, a dialog is open, or the chart is recalculating. Other reasons
include a missing recording, empty Library or absent marker preview. Read the
status text, finish the interaction and click the intended Explorer's chart.

For multiple Explorers, activate the one you want to control. Never assume that
a preview from another window or recording still applies.

If Analyzer closes, Stream Deck is disabled in Settings, or the connection is
lost, application controls become unavailable. After reconnecting, wait for fresh
values. Commands are not queued or replayed; do not assume an interrupted marker
apply succeeded. Check the marker in Analyzer before retrying.

[Explore recordings](EXPLORER.md) · [Installation and updates](INSTALLATION.md)
