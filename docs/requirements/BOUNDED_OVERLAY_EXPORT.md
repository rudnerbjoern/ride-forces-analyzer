# Full-frame and bounded overlay export

Status: steps 1–3 accepted by the owner; steps 4–8 pending.
Content-area export remains planned.

## Requirements

- Export choice: **Full frame** (default) or **Content area**.
- Full frame preserves current canvas dimensions and selected overlay position.
- HUD always uses Full frame; no Content area export.
- Four-panel column supports landscape only. Its Full frame remains 3840 × 2160;
  its rectangular Content area is exactly 960 × 2160, filling the complete 4K height.
  No safety margin, rescaling or canvas enlargement applies to this layout.
- Content area exports only the required layout rectangle plus a safety margin;
  preserve pixel scale, transparency/output mode, frame rate and encoding quality.
- Measure all five layouts in landscape/portrait, including supported positions,
  languages and changing content, text, strokes, shadows and glow.
- Store validated bounds and margin in layout metadata. Start with a 16-pixel
  margin at output resolution; increase where measurements require it. Column uses zero.
- Keep dimensions and crop origin fixed throughout an export. No clipping,
  frame-dependent resizing or movement.
- For Content area, add the safety margin, then round each dimension up to the next
  multiple of 10 pixels: `10 * ceil((content_dimension + 2 * margin) / 10)`.
  Add remaining pixels on the right/bottom; never scale the content. Padding is
  transparent for MOV and black for opaque MP4. Full-frame dimensions remain unchanged.
- Use the same geometry for frames, encoder input/output, layout thumbnails,
  main preview and export summary. Show the actual output dimensions.
- Full-frame previews show the complete canvas and selected placement; Content area
  previews show only the exported rectangle including its margin. HUD thumbnails
  always show the full canvas.
- Layout, format or extent changes refresh previews. Preview backgrounds remain
  presentation-only. Content area must not be padded back to a full-frame video.
- File-size estimates use the selected extent's resolved output dimensions,
  active content and safety margin, including codec alignment; never assume a 4K canvas.
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
  bounds, margins, supported formats, positions and export-area capabilities.
- No layout may depend on another layout. Reusable geometry, margin handling,
  validation and rendering helpers belong to shared central implementations,
  usable by plugins and export consumers without duplicated logic.
- Resolve capabilities through the common plugin contract. HUD declares Full-frame-only
  support in its metadata; dialog, previews and encoder must not hard-code layout names.

## Planned output dimensions

Content-area sizes include a 16-pixel margin on each side and rounding up to 10 pixels,
except the rectangular Column, which has no margin or added padding.
HUD retains its native Full-frame size.

| Layout             | Landscape output | Portrait output |
| ------------------ | ---------------- | --------------- |
| Flow Ribbon        | 3110 × 400       | 1720 × 2280     |
| Corner Instruments | 880 × 1160       | 1720 × 2280     |
| G-Orbit            | 830 × 830        | 1220 × 1220     |
| Four-panel column  | 960 × 2160       | Unsupported     |
| HUD (Full frame)   | 1920 × 1080      | 1080 × 1920     |

Bounds use the existing output pixel scale. G-Orbit landscape uses its measured
796 × 796 alpha rectangle; portrait resampling fills its 1188 × 1188 region.
Other cropped layouts use their complete declared region. Column keeps its complete
960 × 2160 rectangle without growing beyond the 4K height.

## Export assistant

- One dialog: presets/thumbnails above, settings left, large preview right.
- Keep Force display and Encoding sections; no editable safety-margin field.
- Export settings order and visibility:

| Order | Property          | Full frame                             | Content area                       |
| ----- | ----------------- | -------------------------------------- | ---------------------------------- |
| 1     | Layout            | Select                                 | Select                             |
| 2     | Layout format     | Landscape / portrait                   | Landscape / portrait               |
| 3     | Export area       | Full frame selected                    | Content area selected              |
| 4     | Position          | Supported placements                   | Hidden; ignored by output/previews |
| 5     | Output dimensions | Read-only canvas size                  | Read-only bounds including margin  |
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
2. **Measure bounds.** Measure supported layout/format variants and safety margins.
   Acceptance: dimension table and boundary previews, including text/effect extremes;
   HUD remains full-frame. No application changes.
3. **Model geometry.** Extend the existing plugin contract with typed extent capabilities,
   layout-owned geometry and extent/codec-specific estimate rates; implement common
   resolution/validation centrally.
   Acceptance: resolved-size examples and focused contract tests for fixed bounds,
   margins, rounding up to 10 pixels, codec alignment, position independence and HUD restrictions. Review
   dependency direction: plugins use shared helpers, never other layout plugins.
4. **Render and encode.** Apply geometry to frame generation and both output modes.
   Acceptance: short full-frame/content-area videos, verified dimensions/transparency
   and a ten-frame ProRes size comparison. Full-frame output remains unchanged.
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
