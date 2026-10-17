# Ride Forces Analyzer

Offline Windows desktop project for importing Ride Forces (`.forces`) recordings,
analyzing G-force traces and producing charts and transparent video overlays.

## Current capabilities

- **Lossless import:** offline [Path/bytes service](docs/development/IMPORT_SERVICE.md)
  retains original bytes, metadata/weather, ordered attributes, GPS and diagnostics.
- **Analysis primitives:** immutable [models](docs/development/ANALYSIS_MODELS.md),
  explicit unit conversion, device-vector norms and opt-in provisional frame math.
  General physical rider qualification remains open.
- **Calibrated forces:** enabled by default for any imported recording with usable
  direction vectors, using source projections and a configurable centered mean
  (default: 11 samples).
  Positive/negative lateral values mean right/left; positive/negative longitudinal
  values mean acceleration/braking. Labels show these signs in the chart and readout.
  Missing/invalid calibration data leave raw x/y/z available with an explanation.
  See [source-app comparisons and processing policy](docs/validation/APP_REFERENCE.md).
- **Focus workspace:** a dark chart-first layout with a right inspector for display,
  selection and metadata; current values sit below the chart and technical details
  stay collapsible. Small windows switch between chart and inspector.
- **Raw explorer implemented:** open local recordings, inspect x/y/z curves,
  navigate samples, zoom and select an inclusive interval. Import runs in the background.
- **M3 complete (reduced scope):** selected-range minimum/maximum per axis with
  sample/replay/recording time, current raw/calibrated mode and smoothing context.
  Values update on selection, smoothing or recording changes in **Selection extrema**.
  [Acceptance](docs/validation/M3.md) records focused native Windows verification.
  Extra filters, general scientific calibration, events and broad statistics are deferred;
  analytical GPS is outside current scope.
- **Planned product work:** persistent ride library, playback, rendering, video
  synchronization and standalone release.

The **Smoothing** slider offers odd windows from 1 (off) to 51 samples. A new
recording starts at 11; right-click the slider to restore 11. Changes update the curves while dragging
and preserve original values.
The label shows the window and its time support at the actual sample rate.
Stronger smoothing can reduce short force peaks. Calibrated charts always show
the labeled reference levels -1 g, 0 g and +1 g.

The explorer labels replay time as `MM:SS.ff`, where `ff` is the sample counter
within the second at the displayed sample rate. Replay zero is the start marker;
recording-origin seconds remain available in the readout. Raw views retain unknown units and
rider directions explicit. Original files are never changed.
Acceptance and remaining stages are tracked in the [roadmap](docs/ROADMAP.md).

## Install and start

Windows 10/11 x64 with a desktop session is required. From Windows PowerShell:

```powershell
.\setup.ps1
.\start.ps1
```

Setup obtains uv 0.13.0 if needed, installs Python from `.python-version` and
synchronizes the locked Python environment, including development and optional
analysis/render packages. Downloads require network access; installed processing
and startup work offline. Start waits until the window closes. Click **Open recording** (Ctrl+O), choose a
`.forces` file and explore the three colored curves. Use the mouse wheel over the chart or drag to zoom in time, move the
sample slider to inspect values, or enter a start/end selection and click
**Zoom to selection**. **Select visible range** turns a zoomed viewport into a
selection; **Reset view** restores the start/end marker interval (recording limits when
a boundary is absent). Zoom-out can still show the complete recording. Stored start/end and available
gravity/incline markers appear as labeled vertical lines. Available Ride, Park,
Train, Row and Seat metadata appears in the inspector’s **Recording** section. Import notes explain optional-data
warnings; technical details are expandable. The **Inspector** button toggles the
side panel (or switches views in compact windows). **GPS overview** opens a separate offline, north-up route window when usable
GPS positions exist. It marks start/end, retains spatial proportions and leaves
missing fixes/time gaps disconnected. GPS is an approximate location reference,
independent of force measurement; no background map or speed color contract is assumed.
See the [verified first-slice scope](docs/validation/RAW_EXPLORER.md).

For Node development tools, install the Node.js version from `.node-version`
with bundled npm, then run `.\setup.ps1 -Development`.
See [Windows setup](docs/development/SETUP.md) for checks, troubleshooting and
VS Code interpreter/Test Explorer settings. Node is not an application dependency.
FFmpeg is planned for later export work.

## Documentation and data

- [Documentation index](docs/README.md): requirements, API guides, plans and evidence.
- [arc42 architecture](docs/architecture/README.md): subsystem boundaries and decisions.
- [AGENTS.md](AGENTS.md): project rules and Git authorization.
- [Recording catalog](docs/development/RECORDINGS.md): five authorized originals,
  publication authorization and pinned byte lengths/SHA-256 digests. All originals,
  including GPS, metadata and unknown fields, remain read-only.
