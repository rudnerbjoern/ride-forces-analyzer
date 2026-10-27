# 1. Introduction and Goals

[Architecture index](README.md)

## Requirements overview

Ride Forces Analyzer is an offline desktop application for Windows, Linux and
macOS. It imports `.forces` and `.zforces` recordings from Ride Forces and the
supported RFDB profile, preserves original data and provides:

- Raw and calibrated force charts, configurable smoothing, visible-range extrema,
  provisional airtime context and an approximate GPS overview.
- Sample playback, editable ride/calibration markers and independent recording windows.
- Five video-overlay layouts in supported landscape/portrait formats, transparent MOV or opaque
  MP4 output, saved presets and sequential batches. HUD exports native HD;
  the other layouts offer 4K Full-frame or native Content-area output.
- CSV, app-shaped JSON and Analyzer JSON sample exports.

Sensor capture and video synchronization are outside scope. Users align exported
overlays in their video editor. The [roadmap](../ROADMAP.md) owns remaining work;
[user guides](../README.md#for-users) own operation.

## Quality goals

1. Preserve original bytes, unknown fields and source provenance.
2. Keep recording processing offline and independent of optional network services.
3. Separate domain, analysis, presentation, rendering and encoding.
4. Return explicit failure and missing-data states; never fabricate measurements.
5. Distinguish the adopted display policy from qualified physical interpretation.

[Chapter 10](10_quality_requirements.md) defines verification responsibilities.

## Stakeholders

| Role            | Expectation                                                         |
| --------------- | ------------------------------------------------------------------- |
| Recording owner | Local processing, unchanged originals and understandable results    |
| Video creator   | Readable overlays, transparent output and manual editor alignment   |
| Maintainer      | Typed boundaries, reproducible builds and focused regression checks |
| Project owner   | Explicit scope and delivery authorization                           |
