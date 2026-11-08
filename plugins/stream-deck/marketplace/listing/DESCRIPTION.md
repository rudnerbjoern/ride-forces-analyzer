# Ride Forces Analyzer

Bring your ride recordings to your Stream Deck. Browse your Library, replay a ride, explore the force curves and prepare
marker changes with dedicated keys, dials and touch controls.

This plugin connects to Ride Forces Analyzer, the free, open-source desktop application for exploring .forces and .zforces
recordings from the Ride Forces app. Use your Stream Deck alongside the chart and see the application's current state
directly on your controls.

## Explore your recordings

- **Browse your Library:** select recordings, open them in the current Explorer or an additional window, and open the import
  dialog. On Plus, filter by park or workflow status and reset your Library filters.
- **Control playback:** play or pause, change playback speed and move through samples. Plus offers Fine, Medium and Coarse
  steps of 1, 10 or 20 samples per dial notch.
- **Focus on the detail:** zoom the time axis, reset the view, adjust a selection's start and end, and fit the chart to that
  selection.
- **Choose your view:** show or hide vertical, lateral, longitudinal and combined force curves, switch between Raw and
  Calibrated display, and adjust smoothing in Calibrated mode.
- **Prepare marker changes:** preview Start, Gravity, Incline and End positions before applying them. Check the proposed
  position against the applied marker, apply a change when ready, or discard the preview. Applied markers are saved for
  that Library recording.
- **Follow confirmed state:** playback, smoothing, selected recordings, filter choices and marker states follow Analyzer,
  including changes made with the mouse. Preview, pending, applied, unavailable and failed states remain distinguishable.

## Profiles included

**Stream Deck +:** six native pages for Library, Playback/Navigate, Playback/Selection, Curves, Markers/Markers and
Markers/View. The fixed menu keeps the main areas within reach. Use the four dials for contextual navigation and adjustments;
the touch strip displays values, status and action hints.

**Stream Deck Neo:** a key-based Library/Explorer layout with dedicated playback, view and marker pages. The InfoBar shows
contextual information, while the two Touch Points move between native pages.

**Stream Deck Mobile:** a reduced six-key preview with Start, Library, Playback and View pages. It provides basic controls;
the Plus dial features and Neo InfoBar are not available in this profile.

Available controls depend on your device and selected profile.

## Get started

1. Install Ride Forces Analyzer 2.1.0 and this plugin, then confirm the bundled profile for your device.
2. In Analyzer, enable **Settings → Application → Enable Stream Deck** and save.
3. Open a recording, bring the intended Analyzer Explorer to the foreground and click the chart.

The connection is local, with no manual port configuration. Keep Analyzer in the foreground when using application controls.
Open dialogs, dropdowns and text editing temporarily lock those controls; the plugin displays their availability.

## Requirements and help

- Ride Forces Analyzer **2.1.0**, installed separately, with Stream Deck integration enabled.
- Stream Deck software **7.6 or newer**.
- **Windows 10 or later**, or **macOS 15 or later**.
- A device matching the selected bundled profile. Pair Mobile with the desktop Stream Deck app first.

Find the free, open-source application on **GitHub**: search for **ride-forces-analyzer** by **rudnerbjoern**. Open the
repository's **Releases** section to download the desktop application. Its **README** links to the user guides, including
Stream Deck setup and troubleshooting.
