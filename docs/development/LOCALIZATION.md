# Localization

<!-- cspell:words Schwerkraft Neigung Neigungsmarkierung -->

For changing application language and appearance, see the
[user explorer guide](../user/EXPLORER.md#adjust-smoothing-and-display).

The application supports English, German and French offline.
Settings → Application provides language and appearance choices. Save applies
them immediately; Cancel preserves the active settings. Language and light/dark appearance
are saved in local `preferences.sqlite3` and restored on startup. Without valid
preferences, the preferred OS display language selects its registered language
(including regional variants such as fr-CA); unsupported primary languages fall
back to English. Appearance defaults to System, following Windows' effective light/dark
scheme at startup and when it changes (including OS-scheduled changes). An unknown
system scheme falls back to dark. Explicit Dark/Light choices override Windows;
selecting System restores automatic following. An explicit `AppSettings(language="de")`
overrides the saved language for startup; subsequent choices in Settings are saved.
All registered languages support the appearance themes and compact explorer layout.
Preference validation and storage fallback rules belong to the
[runtime contracts](CODE_QUALITY.md#runtime-and-static-contracts).
Dropdown widths follow their complete item texts, including after language
changes; translated choices retain room for the dropdown arrow. Saved preset
prompts participate in the same live translation bindings.
The export assistant scrolls its content when space is limited, keeping navigation
and export actions visible, including at 200% Windows scaling.

## Text ownership

- `i18n.Language` declares supported codes; `LANGUAGES` registers their native
  names, locales, number separators, application catalogs and diagnostic catalogs.
  Settings, OS-language matching, storage validation and export selectors use this
  shared registration; selector indices preserve English, German, French order.
- English templates are stable keys. German uses `translations_de.py`; French uses
  `translations_fr.py`. Entries use concise labels and matching positional
  placeholders. `i18n.tr` separates text
  from opaque values, so recording names, paths and preset/batch names are never
  translated or interpreted as format strings.
- CSpell checks `translations_de.py` with English/German and `translations_fr.py`
  with English/French using locked dictionaries. Legitimate technical compounds
  are scoped to their catalog file. Catalog tests
  check completeness and placeholders independently of spelling.
- German numeric formatting uses decimal commas and grouping dots; French uses
  decimal commas and narrow non-breaking grouping spaces (U+202F). Source numeric
  tokens, units and `MM:SS.ff` sample counters are not localized or parsed again.
- Chart labels and tooltips use Start/End/Gravity/Incline marker names rather than
  JSON field names. German uses Start-/End-/Schwerkraft-/Neigungsmarkierung;
  menu actions and calibration explanations use Schwerkraft and Neigung consistently.
- `ui.translation` binds Qt text properties, combo entries and table headers.
  Language changes update these bindings and the explorer's dynamic presentation,
  preserving data identity, smoothing, cursor, selections and viewport.
  The installed Qt catalog for the selected language supplies standard Qt
  dialog/button text.
- Diagnostic codes, JSON paths and original diagnostic objects/messages remain
  unchanged. Each translated catalog provides code-specific explanations; the original
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
Keep every registered translated catalog complete and preserve English fallback.
Rendering must pass
the language from ExportSettings rather than read the current UI locale.

To add a language, extend `Language`, provide its application/diagnostic catalogs
and register one `LanguageDefinition`. No additional language-specific selector or
storage branches are required. Add locale, persistence and representative UI/export
checks. Catalog tests check all entries together per language, including keys and
placeholders. This lightweight catalog does not provide general plural-rule or
context-disambiguation tooling; use complete explicit singular/plural templates.

Add regression coverage for placeholder compatibility, source preservation and
new visible behavior. Inspect localized layouts on native Windows, including compact
windows and both export aspects. Production glyph bounds, preview consistency,
explicit saved-language round trips and representative real encodes are covered
by the localization and rendering regression suites. No source-app scientific
semantics or milestone status changes are implied by localization.
