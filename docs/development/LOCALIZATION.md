# English and German presentation

The application supports English and German offline, with no new dependencies.
Settings → Application provides language and appearance choices. Save applies
them immediately; Cancel preserves the active settings. Language and light/dark appearance
are saved in local `preferences.sqlite3` and restored on startup. Without valid
preferences, the preferred Windows display language selects German when its
language is German (including regional variants); all other languages fall back
to English. Appearance defaults to System, following Windows' effective light/dark
scheme at startup and when it changes (including OS-scheduled changes). An unknown
system scheme falls back to dark. Explicit Dark/Light choices override Windows;
selecting System restores automatic following. An explicit `AppSettings(language="de")`
overrides the saved language for startup; subsequent choices in Settings are saved.
Both languages support the light/dark schemes and compact explorer layout.
Dropdown widths follow their complete item texts, including after language
changes; translated choices retain room for the dropdown arrow. Saved preset
prompts participate in the same live translation bindings.
The export assistant scrolls its content when space is limited, keeping navigation
and export actions visible, including at 200% Windows scaling.

## Text ownership

- English templates are stable keys in `translations.py`; German entries use
  concise labels and matching positional placeholders. `i18n.tr` separates text
  from opaque values, so recording names, paths and preset/batch names are never
  translated or interpreted as format strings.
- German numeric formatting uses decimal commas and grouping dots. Source numeric
  tokens, units and `MM:SS.ff` sample counters are not localized or parsed again.
- `ui.translation` binds Qt text properties, combo entries and table headers.
  Language changes update these bindings and the explorer's dynamic presentation,
  preserving data identity, smoothing, cursor, selections and viewport.
  The installed Qt German catalog supplies standard Qt dialog/button text.
- Diagnostic codes, JSON paths and original diagnostic objects/messages remain
  unchanged. German notes provide code-specific explanations; the original
  technical text is explicitly selectable. Native OS dialogs follow platform
  rules; external encoder/runtime details may remain in their original language.
- Export settings store a separate `language` field. New assistants initially use
  the UI language, while loaded presets restore their saved choice. Rendering,
  previews and batch snapshots use that explicit language; old records default
  to English. UI switching never changes an existing saved job.

## Maintaining translations

Use `tr("Template {0}", value)` for application text, with complete sentences and
matching placeholders. Bind widget text through the existing Qt helper; do not
translate source identifiers, object names, enum keys, filenames or user content.
Add German catalog entries and keep English fallback usable. Rendering must pass
the language from ExportSettings rather than read the current UI locale.

Add regression coverage for placeholder compatibility, source preservation and
new visible behavior. Inspect German layouts on native Windows, including compact
windows and both export aspects. Production glyph bounds, preview consistency,
saved language/default compatibility and representative real encodes are covered
by the localization and rendering regression suites. No source-app scientific
semantics or milestone status changes are implied by localization.
