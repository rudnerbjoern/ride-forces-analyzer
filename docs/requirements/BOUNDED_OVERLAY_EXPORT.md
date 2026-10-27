# Full-frame and bounded overlay export

Status: steps 1–7 accepted by the owner; step 8 pending.
Native Content-area geometry and rendering/encoding are implemented and locally validated.
Geometry-aware previews, localized assistant controls and preset/job area restoration
are available. Batch execution uses each saved job's bound export area.

## Requirements

- Export choice: **Full frame** (default) or **Content area**.
- Full frame preserves current canvas dimensions and selected overlay position.
- HUD always uses Full frame; no Content area export.
- Four-panel column supports landscape only. Its Full frame remains 3840 × 2160;
  its rectangular Content area is exactly 960 × 2160, filling the complete 4K height.
  No safety margin, rescaling or canvas enlargement applies to this layout.
- Content area exports the complete native layout image directly, including its
  existing empty/transparent pixels. Preserve transparency/output mode, frame rate
  and encoding quality.
- Verify all five layouts in landscape/portrait, including supported positions,
  languages and changing content, text, strokes, shadows and glow.
- Store exact native dimensions in layout metadata. Do not crop, scale, add safety
  margins/padding or round dimensions. Both encoder input and output use these sizes.
- Native dimensions must be positive even integers for the supported codecs.
  Reject invalid metadata or renderer-size mismatches rather than changing images.
- Keep dimensions fixed throughout an export. No clipping,
  frame-dependent resizing or movement.
- Content area uses no geometric FFmpeg filter. Opaque output retains its black
  background. Full-frame scaling, placement and canvas dimensions remain unchanged.
- Use the same geometry for frames, encoder input/output, layout thumbnails,
  main preview and export summary. Show the actual output dimensions.
- Full-frame previews show the complete canvas and selected placement; Content area
  previews show the complete native layout image. HUD thumbnails
  always show the full canvas.
- Layout, format or extent changes refresh previews. Preview backgrounds remain
  presentation-only. Content area must not be padded back to a full-frame video.
- File-size estimates use the selected extent's exact output dimensions and active
  content; never assume a 4K canvas for Content area.
- Each plugin may supply codec-specific estimate rates for Full frame and Content area
  independently. Unmeasured combinations use a shared approximate fallback, not
  fabricated measurements or a simple proportional reduction of the full-frame file size.
- Refresh estimates in settings and review after layout, format or extent changes.
  HUD estimates always use Full frame.
- Persist the choice in presets and bound batch jobs; omitted values use Full frame.
- Explain in the user guide: bounded videos require positioning in the video editor;
  the original full-frame placement is not represented by empty video pixels.
- Reuse existing rendering/encoding boundaries; no new output format or dependency.
- Preserve the existing plugin model: each layout owns its drawing functions,
  native dimensions, supported formats, positions and export-area capabilities.
- No layout may depend on another layout. Reusable geometry,
  validation and rendering helpers belong to shared central implementations,
  usable by plugins and export consumers without duplicated logic.
- Resolve capabilities through the common plugin contract. HUD declares Full-frame-only
  support in its metadata; dialog, previews and encoder must not hard-code layout names.

## Planned output dimensions

Content-area sizes equal the layout renderer's complete native image.
HUD retains its native Full-frame size.

| Layout             | Landscape output | Portrait output |
| ------------------ | ---------------- | --------------- |
| Flow Ribbon        | 3072 × 360       | 840 × 1120      |
| Corner Instruments | 840 × 1120       | 840 × 1120      |
| G-Orbit            | 800 × 800        | 800 × 800       |
| Four-panel column  | 960 × 2160       | Unsupported     |
| HUD (Full frame)   | 1920 × 1080      | 1080 × 1920     |

Content-area sizes are independent of Full-frame placement/scaling. Portrait
Content area does not enlarge the native image to its Full-frame region size.
Column keeps its complete 960 × 2160 rectangle without growing beyond the 4K height.

## Export assistant

- One dialog: presets/thumbnails above, settings left, large preview right.
- Keep Force display and Encoding sections.
- Export settings order and visibility:

| Order | Property          | Full frame                             | Content area                       |
| ----- | ----------------- | -------------------------------------- | ---------------------------------- |
| 1     | Layout            | Select                                 | Select                             |
| 2     | Layout format     | Landscape / portrait                   | Landscape / portrait               |
| 3     | Export area       | Full frame selected                    | Content area selected              |
| 4     | Position          | Supported placements                   | Hidden; ignored by output/previews |
| 5     | Output dimensions | Read-only canvas size                  | Read-only native dimensions        |
| 6     | Output            | Transparent MOV / opaque MP4           | Same choices                       |
| 7     | Overlay language  | Select                                 | Select                             |
| 8     | Frame rate        | Select                                 | Select                             |
| 9     | Ride range        | Markers / selection / entire recording | Same choices                       |

- Rename Video format to Layout format: it controls layout arrangement; Content area
  output need not have a 16:9 or 9:16 aspect ratio.
- HUD replaces Export area selection with a fixed Full frame label and hides Position.
- Layout availability follows plugin-supported formats; Column is unavailable in portrait.
- Retain the chosen position when switching to Content area; restore it on return.
- Review shows export area and actual dimensions; show Position only for applicable
  Full-frame layouts.

## Implementation steps

Approval gate: complete one step, run its focused checks, present its deliverable
and wait for explicit owner acceptance before starting the next step. Keep temporary
measurement tables, images and videos in `.tmp/`; no separate historical reports.

1. **Verify existing plugin boundaries.** Inspect all five layouts, the common contract,
   registry and consumers before adding export-area behavior. Check layout-owned
   properties/functions, cross-layout dependencies and shared helper ownership.
   Resolve boundary violations with behavior-preserving changes limited to this scope.
   Acceptance: concise dependency/ownership findings, any required corrections and
   focused regression checks; owner confirms the existing plugin boundaries are sound.
2. **Verify native output.** Verify supported layout/format variants and native sizes.
   Acceptance: dimension table and boundary previews, including text/effect extremes;
   HUD remains full-frame. No application changes.
3. **Model geometry.** Extend the existing plugin contract with typed extent capabilities,
   layout-owned geometry and extent/codec-specific estimate rates; implement common
   resolution/validation centrally.
   Acceptance: resolved-size examples and focused contract tests for exact native sizes,
   even codec dimensions, position independence and HUD restrictions. Review
   dependency direction: plugins use shared helpers, never other layout plugins.
4. **Render and encode.** Pass complete native layout images directly to encoding
   for Content area, without cropping/scaling/padding/rounding, in both output modes.
   Use measured test-export bytes, frame counts and actual dimensions to populate
   rough lower/upper size-estimate rates in the owning plugin, separately for each
   tested codec and extent. Retain measurement conditions/limits with the rates;
   leave untested combinations on the shared fallback.
   Preserve HUD's existing full-ride calibration; use the same rates for CPU and GPU.
   Short HUD exports verify rendering/encoding only and do not change its rates.
   Acceptance: short full-frame/content-area videos, verified dimensions/transparency
   and a ten-frame ProRes size comparison; plugin estimates reflect those exports
   as approximate ranges. Full-frame output remains unchanged.
5. **Prepare previews.** Adapt thumbnail and main-preview generation to output geometry.
   Acceptance: paired preview images matching the encoded output, including HUD and
   preview refresh after layout/format/extent changes.
6. **Connect the assistant.** Add localized controls, property order, visibility and
   review fields using plugin capabilities. Acceptance: interactive review of both
   modes, HUD, position restoration, actual dimensions and matching file-size estimates;
   focused UI checks, including estimate updates when changing extent.
7. **Persist and batch.** Store extent in presets/jobs and use it during batch execution.
   Acceptance: save/reopen and mixed-mode batch examples; omitted extent defaults to
   Full frame. Verify HUD handling and independent saved job snapshots.
8. **Validate and document.** Check the combined workflow and update maintained
   layout/export/user contracts. Acceptance: relevant checks pass and documentation
   matches the reviewed behavior; report any remaining limitations.

References: [layout API](../development/EXPORT_LAYOUTS.md),
[export contract](../implementation/VIDEO_EXPORT.md),
[presets and batches](../implementation/EXPORT_BATCHES.md).
