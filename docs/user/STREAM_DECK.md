# Control Analyzer with Stream Deck +, Neo and Mobile

Use the plugin to browse your Library, control playback and view settings, and
prepare or apply recording markers. The currently active Analyzer Explorer is
the target; device commands do not open a second window.

The Plus and Neo profiles use the same colored icons and short key captions.
The examples use the English plugin labels. The Analyzer can use its own selected
interface language. The Windows backend and plugin software are tested; physical Plus operation
remains unverified. Neo import and hardware operation, and macOS acceptance, remain open.

## Set up the controls

1. Install the plugin using the current [local Windows setup](../../plugins/stream-deck/README.md#local-build-and-installation).
   A downloadable release installer is not available yet.
2. Open `plus.streamDeckProfile` for **Stream Deck +**, or `neo.streamDeckProfile`
   for **Neo**, and choose the matching connected device in the import dialog.
   Existing profiles remain available.
   Menu graphics are embedded in the profile: reimport the updated profile to
   refresh them; restarting the plugin alone only refreshes dynamic controls.
3. In Analyzer, enable **Settings → Application → Enable Stream Deck** and save.
4. Select **Ride Forces Analyzer +** or **Ride Forces Analyzer Neo** in Stream Deck. On Start, select **Start app**
   in the software preview and choose your Analyzer EXE or a Windows shortcut in
   the native **Open** action's file field. The bundled profile leaves this path
   empty because it depends on your installation. The port discovery file does
   not contain an executable path.
5. Bring the intended Analyzer Explorer to the foreground and click the chart.

Operate the **physical LCD keys, dials and touch strip**. Clicking a key in the
Stream Deck desktop application's preview selects its configuration; it does not
execute that key. Keep Analyzer in the foreground when testing application controls.

## macOS availability

The plugin manifest permits **macOS 15+** with **Stream Deck 7.6+**. The same
JavaScript plugin and profiles are prepared for installation there. Native Mac
installation, connection, focus handling and device operation are **unverified**.
Use the Mac Analyzer `.app` and set **Start app** to that `.app` in Stream Deck;
the Windows EXE/shortcut instructions above apply only to Windows.

## Recognize the functions and states

![Stream Deck Plus software illustration of all seven profile pages, two rows of four keys, aligned touch-strip fields and four dials](../images/stream-deck-plus-controls.png)

*Software illustration from all seven actual generated Plus profile pages and
production plugin feedback. Each panel shows its keys, touch strip and four dials.
All values and marker states are examples, not a device photograph or a hardware test. [Open the full-size image](../images/stream-deck-plus-controls.png).*

The colored illustration identifies the function. A separate badge indicates its
current state; a dimmed icon can still show the last confirmed value.

| Badge / state            | Meaning                                                           |
| ------------------------ | ----------------------------------------------------------------- |
| Neutral dot              | Ready, or a toggle currently off. Check the displayed value.      |
| Green check              | Active toggle or a confirmed applied marker.                      |
| Purple pencil            | Marker preview; the proposed value has not been applied.          |
| Blue clock               | Request or marker adoption is pending. Wait for confirmation.     |
| Red cross                | Request or analysis failed; the last applied value remains valid. |
| Amber lock               | Control unavailable; the text gives the reason.                   |
| Gray disconnected symbol | No usable connection. Cached values are cleared.                  |

A press or acknowledgement does not turn a toggle on by itself. The display follows
confirmed program state, including changes you make with the mouse in Analyzer.

## Move through the menus

**Start** offers **Start app**, **Library**, **Explorer** and **Website** from left
to right. **Start app** uses the configured native Open action; **Website** opens
the [project website](https://rudnerbjoern.github.io/ride-forces-analyzer/) in your
browser. Both work without an Analyzer connection. Explorer contains **Playback**,
**Curves** and **Markers** in a central group. Plus also has **Selection**.

In each Plus/Neo submenu, **Back** is key **1** (top-left) and **Home** is key **8**
(bottom-right). Home returns to Start. Keys are numbered left to right, top row
first. Start has no Back or Home key. Fine/Coarse stays on key **6** on Playback,
Selection and Markers. Key captions use two short lines; detailed values remain
on the touch strip. Menu navigation remains available while
Analyzer is disconnected or application commands are blocked.

## Browse and open Library recordings

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

| Dial         | Turn                                             | Press            | Touch-strip information                               |
| ------------ | ------------------------------------------------ | ---------------- | ----------------------------------------------------- |
| 1 · Position | Move through source samples; stop at the bounds. | Play/pause.      | Sample, replay time, play state and Fine/Coarse mode. |
| 2 · View     | Zoom the time axis.                              | Reset view.      | Actual visible interval and its duration in seconds.  |
| 3 · Speed    | Select the next supported playback speed.        | Return to 1×.    | Actual speed and play/pause state.                    |

**Fine / Coarse** switches Position, Selection and marker dials between **1** and
**10 source samples per notch**. It starts in Fine mode, survives menu changes and never
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

Press **Zoom / Selection** on key **5** to fit the chart to that range. GUI selection changes
also appear on the touch strip. These controls do not move the replay cursor or
change recording markers, calibration, stored Library bounds or analysis.

## Preview, apply or discard markers

Open **Explorer → Markers**. Dial order is **Start, Gravity, Incline, End**.

1. **Turn** a dial to change only that marker's preview. This pauses playback;
   analysis and stored markers remain unchanged.
2. Check the sample/time and the **Preview** status. The separate **Applied** line
   retains the last adopted value.
3. **Press** that dial to apply its preview. **Pending** lasts until analysis is
   adopted. **Applied** confirms success; **Failed** retains the previous value.
4. **Tap the corresponding touch field** to discard only its preview.

Start cannot pass End, and End cannot pass Start. Gravity and Incline may lie
outside Start/End but must remain inside the source recording. If either reference
is unset, place it in Analyzer first.

Previews survive menu changes. Opening another recording or changing the target
Explorer clears them. Applying or discarding one marker does not confirm the
others and does not resume playback. For archived recordings, successfully adopted
choices use the existing Library persistence.

The Plus Markers page has Back, Home and Fine/Coarse keys alongside its four
dials. It has no additional marker-key editors.

## Neo keys, InfoBar and Touch Points

Neo uses the eight keys instead of dials. Import `neo.streamDeckProfile` when a
Neo is connected. Its Start row is **Start app · Library · Explorer · Website**;
configure the app path once, as described above. The Plus profile is separate.

![Stream Deck Neo software illustration of all fourteen prepared pages, two rows of four keys, contextual InfoBar values and the two native Touch Points](../images/stream-deck-neo-controls.png)

*Software illustration from the actual generated Neo profile and plugin feedback.
All values are fixed examples. No Neo is connected; native import, page switching,
physical legibility and hardware operation remain unverified. [Open full size](../images/stream-deck-neo-controls.png).*

The **left/right Touch Points** are native previous/next-page controls. The
profile provides two main pages: **Start** and **Quick controls**. Quick controls
contains Play/Pause, Zoom −/+, Reset view, Zoom to selection and Reset speed.
They work through existing application commands. The InfoBar itself is display-only;
its action does not receive Touch Point presses. See
[Elgato's Neo controls](https://www.elgato.com/us/en/p/stream-deck-neo) and
[InfoBar API](https://docs.elgato.com/streamdeck/sdk/guides/neo-infobar/).

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
Marker name/state is on the first line, the current preview/adopted position on
the second, and the last applied value on the third. Long text is elided within
the display; disconnected state clears program values. No extra analysis or
commands are triggered by the InfoBar.

## Mobile: limited six-key preview

The prepared **Ride Forces Analyzer Mobile Preview** profile uses **two rows of
three buttons**. Pair Stream Deck Mobile with the Stream Deck desktop app, choose
its six-key layout and import `mobile.streamDeckProfile` onto that Mobile device.
The plugin still requires Stream Deck 7.6 or later and **Enable Stream Deck** in
Analyzer. [Elgato's setup instructions](https://help.elgato.com/hc/en-us/articles/16786832942221-Elgato-Stream-Deck-Mobile-2-0-Getting-Started)
cover pairing; it is handled by Stream Deck, not by an extra Analyzer network server.

![Stream Deck Mobile limited preview showing the four actual six-key pages Start, Library, Playback and View, with Back and no Home button](../images/stream-deck-mobile-controls.png)

*Software illustration from the generated Mobile profile and fixed plugin examples.
Mobile import, pairing and actual phone operation remain unverified.*

- **Start:** Start app, Library, Playback and Website. Configure the Analyzer EXE or
  Windows shortcut on the **desktop** in Start app's native Open settings.
- **Library:** Previous/Next, Open and Import. Browsing follows visible sorting and
  filters; only Open opens the selection in the current Explorer. Keys show short
  action names and the selected index/count; the full recording name stays in
  the Analyzer Library (and on the Plus touch strip or Neo InfoBar).
- **Playback:** Play/Pause, one sample backward/forward, Reset view and the View folder.
- **View:** Zoom −/+, Reset view, Zoom to selection and Play/Pause.

**Back is key 1; there is no Home key.** Key 6 is used for Reset view on Playback
and Play/Pause on View. Library keeps one key free for your own assignment.
This preview omits curve/smoothing/speed editors, markers and manual selection
bounds. The GUI remains available for those controls. The same foreground/focus,
dialog, connection and confirmed-state rules apply to Mobile keys.

## Understand locks and connection changes

Controls are blocked while another application is in front, an Analyzer text/number
field or dropdown has focus, a dialog is open, or analysis is busy. Other reasons
include a missing recording, empty Library or absent marker preview. Read the
status text, finish the interaction and click the intended Explorer's chart.

For multiple Explorers, activate the one you want to control. Never assume that
a preview from another window or recording still applies.

If Analyzer closes, Stream Deck is disabled in Settings, or the connection is
lost, application controls become unavailable. After reconnecting, wait for fresh
values. Commands are not queued or replayed; do not assume an interrupted marker
apply succeeded. Check the adopted marker in Analyzer before retrying.

[Explore recordings](EXPLORER.md) · [Plugin installation and configuration](../../plugins/stream-deck/README.md)
