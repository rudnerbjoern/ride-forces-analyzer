# DEV-REQ-002 Stage 0 inspection — 2026-10-13

Scope: source observations and proposed design contracts only. M2 remains planned;
no production importer, canonical model, resource guard or later stage was started.
Work is on `feat/m2-schema-inventory`, based on main `72b7c9c85ff7c08055a51f8d3ae2221ab2d8a4b9`.
The inspection was performed without staging, committing or publication. The owner
subsequently authorized a Stage 0 commit and push on this feature branch on
2026-10-13, including the supplied Iron Gwazi fixture. No PR or merge is authorized.

## Evidence and reconciliation

The recursive inventory covers every JSON value in the original iPhone quartet
and the additionally owner-supplied Apple Watch Iron Gwazi. It records 34 root
field names, a union of 76 normalized paths, all nested member/type counts and
all sequence lengths. Across five files it visits 357,336 value nodes,
48,029 acceleration vectors, 39,317 gravity vectors and 698 GPS fixes.
The snapshot includes original sizes/hashes without copying GPS traces into logs.

Iron Gwazi has no gravity/GPS arrays or top-level coordinates. The owner confirmed
that Apple Watch and iPhone devices mark data-availability profiles. Earlier
four-file motion/GPS counts and field union remain correct; prefix-only motion evidence is now
exhaustive. [Format analysis](../requirements/FORMAT-ANALYSIS.md) and FR-008/FR-013
now distinguish a valid acceleration-only profile from corrupted supplied arrays.
An Iron Gwazi gravity marker survives even though its gravity array is absent;
marker order and meaning must not be inferred or repaired.
Taron/Voltron Nevera omit sampleRate, correcting the earlier all-present claim.
The owner specified defaults for absent ridingPosition (Seated) and sampleRate
(50 Hz); ADR 0002 keeps these distinct from stored values with explicit provenance.

## Requirement traceability

| Requirement | Stage 0 output                                                                    | Implementation evidence still pending                  |
| ----------- | --------------------------------------------------------------------------------- | ------------------------------------------------------ |
| FR-001      | ADR 0002 defines Path/bytes APIs and pure/IO boundaries                           | Public service and integration tests                   |
| FR-004      | Immutable byte ownership decision; five hash/size/mtime tests; output guard       | Canonical source envelope and exact source round trip  |
| FR-007      | Literal 2.2.0 dispatch/version extension decision; five schema observations       | Version dispatch and unsupported-version errors        |
| FR-024      | Explicit resource/error defaults; lossless inventory decode checks                | Production limits, I/O errors and adversarial tests    |
| FR-030      | Complete path/type/presence snapshot and ADR API/GPS/device policies              | Implemented API documentation and warning contracts    |
| FR-008/013  | Apple Watch optional-gravity decision; requirements reconciled with genuine input | Capability models and present-array pairing validation |
| AC-02       | All five originals retain pinned bytes, length, hash and modification time        | Repeat integrity during each later import stage        |

These are decisions and inspection tests, not claims that the importer requirements
or M2 acceptance criteria are already implemented. See
[ADR 0002](../decisions/0002-forces-source-contract.md) for proposed limits,
source ownership, errors and optional GPS handling.

## Reproduction and validation

Commands run from the repository root with native Windows uv 0.13.0 and Python
3.14.6. Temporary artifacts stay under `.tmp/`; installed quality tools run offline.

```powershell
uv --version
uv run python --version
uv run python tests/fixture_inventory.py --output .tmp/schema-inventory.json
uv run pytest tests/test_fixture_inventory.py tests/test_project.py
```

The original exact-quartet test failed after Iron Gwazi was added, while the
existing four hash checks passed. The inventory was extended with its first
observed hash/size; all original four pins remain unchanged. The initial focused
20-case suite passed; its Pyright check exposed eight optional-TypedDict-access
errors. Those accesses were corrected and Pyright then analyzed 16 files without
errors. A later output-overwrite guard and the 1,001-element late-extension case
extend focused coverage to 21 cases, all passing on Windows. The first broad
run exposed two formatter/COM812 overlaps; shorter expressions resolved them.
The next run passed Python/type/runtime checks but found three CSpell words;
plain wording and a snake_case test name resolved these without weakening checks.

Snapshot regeneration produces a separate file; tests never bless changed source
data automatically. Its schema observations are deterministic UTF-8/LF bytes.
The test helper rejects duplicate members/non-finite constants to avoid lossy
evidence. It is restricted to trusted fixtures and is not the resource-bounded
production decoder. Model/time/memory benchmarking remains for later stages.

Final applicable project checks passed under native Windows after the focused
21-case inventory/integrity suite. The final documentation edit initially exposed
one duplicate blank line; it was removed and the focused documentation/workflow
suite passed again. Ruff's configured COM812/formatter warning remains expected.

| Command                                                      | Actual final result                                      |
| ------------------------------------------------------------ | -------------------------------------------------------- |
| `uv lock --check`                                            | 32 packages resolved; lock consistent                    |
| `uv run ruff check .`                                        | All checks passed                                        |
| `uv run ruff format --check src tests`                       | 16 files already formatted                               |
| `uv run mypy src`                                            | No issues in 10 source files                             |
| `npm run typecheck -- --outputjson`                          | 16 files analyzed; 0 errors/warnings                     |
| `npm run test:types`                                         | 3 passed                                                 |
| `npm run test:dependencies`                                  | 6 passed                                                 |
| `uv run pytest`                                              | 54 passed on win32 / Python 3.14.6; 2 native GUI cases   |
| `npm run test:docs`                                          | 23 Markdown/link cases passed; CSpell 51 files, 0 issues |
| `.tmp/m1-actionlint/actionlint.exe .github/workflows/ci.yml` | No diagnostics; exit 0                                   |

Snapshot regeneration was repeated with the final utility; its 95,346 bytes
match the expected artifact exactly, SHA-256
`600aaf8b22e6f688487c5d24c50de30b56b9afdf06ae517e2eab2f7cf2b2a8b7`.
The independent final command `uv run python .tmp/stage0-confirm.py` confirmed
all five original sizes, SHA-256 values and modification times against before
snapshots. The temporary verifier remains ignored under `.tmp/`.

## Changed files

New inspection artifacts:

- `tests/fixture_inventory.py`
- `tests/test_fixture_inventory.py`
- `tests/fixtures/schema-inventory.json`
- `docs/decisions/0002-forces-source-contract.md`
- `docs/validation/M2_STAGE0.md`

Adjusted for the fifth fixture, proposed contracts, owner defaults and navigation:

- `tests/test_project.py`
- `.cspell.json` (the proper name Gwazi)
- `AGENTS.md`, `README.md`, `docs/README.md`, `docs/ROADMAP.md`
- `docs/architecture/OVERVIEW.md`
- `docs/development/RECORDINGS.md`
- `docs/requirements/DEV-REQ-002-forces-importer.md`
- `docs/requirements/FORMAT-ANALYSIS.md`
- `docs/implementation/DEV-REQ-002/PLAN.md`
- `docs/implementation/DEV-REQ-002/PROMPTS.md`

Iron Gwazi was supplied by the owner, not created or edited by this work. No
original `.forces` file or production Python module changed. No dependency was added.

## Integrity and boundaries

Independent before/after snapshots under `.tmp/` record each original byte length,
SHA-256 and modification time. Existing original-quartet regression pins are
unchanged; Iron Gwazi is pinned at 346,781 bytes and
`cfea878d208ca082c41562084c9d5b3635c4ac1de6e6c583cee17e53d0becbcb`.
The [recording catalog](../development/RECORDINGS.md) retains the other four digests.
The original recordings are input only; no GPS data was normalized or removed.
OS-managed access-time behavior is not asserted by a read-only test.

The device-profile rule is owner-confirmed. Exact future optionality, numeric
epochs, endIndex interpretation, axes, calibration, GPS units/sentinels and
source extrema remain unverified. Resource defaults are design choices requiring
boundary tests and later Windows performance measurements. Proposed diagnostics
and immutable model behavior have not been exercised by an importer.

No hosted CI or fresh interactive VS Code discovery is claimed for this stage.
Iron Gwazi was supplied as an untracked original; the owner subsequently authorized
its inclusion in the Stage 0 branch commit and push. The PR-only CI is not triggered
by this authorized publication, which explicitly excludes PR creation.
Stage 0 evidence is ready for review after local checks; the ADR is proposed,
Stage 1 requires a separate instruction and M2 is not complete. Stop here.
