# Plus integrated acceptance

Verification date: 2026-11-07. Scope: PLUS-06 at `2f50e48`, including marker centering
in the chart, application controller and grouped UI test; Windows 11,
Python 3.14.6, Qt/PySide6 6.12.0 and Node.js 26.11.1; plugin 0.2.1.
Overall status: **Accepted** for Windows Plus. Hardware results are owner-confirmed;
software evidence alone does not establish hardware acceptance.
Requirements and control meanings belong to the [Stream Deck requirements](../requirements/STREAM_DECK.md).

## Software

Successful Windows evidence is reused for unchanged inputs, not repeated after
committing. Contract and locked dependencies are unchanged since `8bfc213`;
plugin/reference checks cover `23fdae9`. Fresh grouped UI, Ruff and application
type checks pass for marker centering. Physical results are recorded separately below.
Temporary runner output remains under `.tmp/`.

| Scope                                       | Checks                                                                                                                                                | Result                                                                                                                        |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Application contract and grouped UI routing | `uv run --locked pytest tests/support/test_control_contract.py tests/ui/test_stream_deck.py`                                                          | 80 passed; includes filters, target validation, focus/dialog locks and shared views                                           |
| Marker-centering regression                 | `uv run --locked pytest tests/ui/test_stream_deck.py`                                                                                                 | Passed on final changes; all four previews, unchanged zoom/visible intervals, both timeline ends and unchanged stored markers |
| Application quality                         | Scoped `ruff check` / `ruff format --check` on contract, controller and paired tests; `uv run --locked mypy src`; `npm run typecheck`                 | Passed; no type errors                                                                                                        |
| Plugin SDK, gestures, profiles and feedback | `node --test plugins/stream-deck/tests/*.test.mjs` after `npm run build:plugin --workspace plugins/stream-deck`                                       | 60 passed; TypeScript compilation, built SDK host and offline archive validation included                                     |
| Official layout validation                  | `npm run validate:plugin --workspace plugins/stream-deck`                                                                                             | Passed                                                                                                                        |
| Reference rendering                         | `uv run --locked pytest plugins/stream-deck/tests/test_reference.py`                                                                                  | Passed; production layouts and fixed software examples                                                                        |
| Reference code quality                      | `uv run --locked ruff check scripts/render_stream_deck_reference.py plugins/stream-deck/tests/test_reference.py`; corresponding `ruff format --check` | Passed                                                                                                                        |
| Documentation                               | `npm run test:docs`; focused Markdown/spelling checks after acceptance wording changes                                                                | Passed                                                                                                                        |
| Native installation and connection          | Native plugin/host logs, developer mode and established localhost connection                                                                          | Verified; installed bundle and both Plus layouts match the tested build                                                       |

Qt/TypeScript transport implementation is unchanged; the separate transport
interoperability suite is outside the affected change scope. No full application
suite, Neo/Mobile or macOS acceptance is claimed.

## Hardware

The owner confirmed the integrated checks, including the remaining boundary,
lock and recovery cases. No repeated hardware run is required for unchanged inputs.

| Area               | Owner-confirmed result                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Menus              | Fixed menu, subgroup recall, native swipes and active-page feedback work                                                                          |
| Library            | Browse/open/new window/import, cyclic order, empty/single-entry results, filters/reset and display-only dial gestures work                        |
| Playback/selection | Dial/key gestures, actual 1/10/20 steps, zoom to selection and selection bounds work                                                              |
| Curves             | Curve/data-mode keys, dial presses/rotation and smoothing endpoints work; hints are understandable                                                |
| Markers            | Independent preview/apply/discard, bounds, menu retention and recording/target clearing work; hidden previews are revealed without changing zoom  |
| Legibility         | Views, four-/five-line arrangements, special states, long-text elision and press-only controls are readable                                       |
| Locks/recovery     | GUI changes reach the device; focus/dialog/background locks and target changes work; reconnect does not replay commands or fabricate confirmation |

No physical Windows Plus observations remain open for PLUS-06. Neo, Mobile,
macOS and native archive installation are outside this acceptance.
