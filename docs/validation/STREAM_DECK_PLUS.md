# Plus integrated acceptance

Verification date: 2026-11-07. Scope: PLUS-06 based on `23fdae9` plus the working-tree
marker-centering change in the chart, application controller and grouped UI test; Windows 11,
Python 3.14.6, Qt/PySide6 6.12.0 and Node.js 26.11.1; plugin 0.2.1.
Overall status: **Partial**. Software evidence does not establish hardware acceptance.
Requirements and control meanings belong to the [Stream Deck requirements](../requirements/STREAM_DECK.md).

## Software

Successful Windows evidence is reused for unchanged inputs, not repeated after
committing. Contract and locked dependencies are unchanged since `8bfc213`;
plugin/reference checks cover `23fdae9`. Fresh grouped UI, Ruff and application
type checks pass for marker centering. The owner confirmed off-screen Start preview
centering with unchanged zoom on Plus; other markers have automated coverage only.
Temporary runner output remains under `.tmp/`.

| Scope | Checks | Result |
| --- | --- | --- |
| Application contract and grouped UI routing | `uv run --locked pytest tests/support/test_control_contract.py tests/ui/test_stream_deck.py` | 80 passed; includes filters, target validation, focus/dialog locks and shared views |
| Marker-centering regression | `uv run --locked pytest tests/ui/test_stream_deck.py` | Passed on final changes; all four previews, unchanged zoom/visible intervals, both timeline ends and unchanged stored markers |
| Application quality | Scoped `ruff check` / `ruff format --check` on contract, controller and paired tests; `uv run --locked mypy src`; `npm run typecheck` | Passed; no type errors |
| Plugin SDK, gestures, profiles and feedback | `node --test plugins/stream-deck/tests/*.test.mjs` after `npm run build:plugin --workspace plugins/stream-deck` | 60 passed; TypeScript compilation, built SDK host and offline archive validation included |
| Official layout validation | `npm run validate:plugin --workspace plugins/stream-deck` | Passed |
| Reference rendering | `uv run --locked pytest plugins/stream-deck/tests/test_reference.py` | Passed; production layouts and fixed software examples |
| Reference code quality | `uv run --locked ruff check scripts/render_stream_deck_reference.py plugins/stream-deck/tests/test_reference.py`; corresponding `ruff format --check` | Passed |
| Documentation | `npm run test:docs`; focused Markdown/spelling checks after acceptance wording changes | Passed |
| Native installation and connection | Native plugin/host logs, developer mode and established localhost connection | Verified; installed bundle and both Plus layouts match the tested build |

Qt/TypeScript transport implementation is unchanged; the separate transport
interoperability suite is outside the affected change scope. No full application
suite, Neo/Mobile or macOS acceptance is claimed.

## Hardware

Only explicit owner confirmations count as physical observations. Earlier
confirmations remain valid for unchanged bindings; rows below retain remaining gaps.

| Area | Confirmed | Open |
| --- | --- | --- |
| Menus | Fixed menu, subgroup recall and native swipe feedback | Full integrated traversal with final visuals |
| Library | Browse/open, cyclic endpoints, single entry; New window opens another recording; Park/Status apply, individual touch resets, bounded choices, page/GUI proposal reset and Reset filters | Final-layout Import/Open keys, empty results and display-only dial gestures |
| Playback/selection | Step key text/icon cycles 1/10/20 | All final dial/key gestures, clamping and selection bounds |
| Curves | Three curve keys and Raw/Calibrated; smoothing reset, Combined toggle, zoom reset and Play/Pause presses; dial 4 position rotation; status and hints understandable | Smoothing rotation and endpoint clamping |
| Markers | Rotation of all four dials creates previews visible in Explorer; menu changes retain them; Gravity press applies only its preview and Incline touch discards only its preview; recording and target changes clear previews without applying/transferring them; off-screen Start preview is centered with unchanged zoom | Remaining individual apply/discard gestures, bounds and physical centering of other markers |
| Legibility | Views, four-/five-line arrangements, special states and long-text elision readable on Plus; Curves status, hints and press-only controls understandable | None for PLUS-05 |
| Locks/recovery | Switching Explorer windows updates the device to the active recording and values without transferring previews | GUI feedback, focus/dialog/background locks and disconnect/reconnect without replay |

PLUS-06 remains incomplete until the open physical observations are confirmed.
