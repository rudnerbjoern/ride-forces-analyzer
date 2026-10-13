# Real recording fixtures

## Authorization and use

The owner expressly authorizes using and publishing all four complete Ride Forces
recordings below in this project for testing and development, including all
embedded data such as authentic GPS positions and metadata. Manta was authorized
with the original M1 fixture; Kraken, Taron and Voltron Nevera were added and
expressly authorized on 2026-10-13.

This authorization covers the listed files. Additional recordings require their
own authorization before inclusion or publication. Keep every `.forces` file
read-only and preserve its original bytes, unknown fields and metadata. Neither
Git nor editor tooling may normalize or reformat these recordings.

## Fixture catalog

The sizes and SHA-256 digests below were computed by reading the original bytes.
They are pinned in `tests/test_project.py`; intentionally replacing a recording
requires reviewing its authorization, tests and this catalog together.

### Kraken

- File: [Kraken-1537D9CF-418B-4F13-AA1A-F303F9DE2311.forces](../../tests/fixtures/real/Kraken-1537D9CF-418B-4F13-AA1A-F303F9DE2311.forces)
- Size: 837779 bytes.
- SHA-256: `f418e8323beeba1ab81da93705b18b0baee3622c2b702ef34b72cd550d45984d`.

### Manta

- File: [Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces](../../tests/fixtures/real/Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces)
- Size: 801293 bytes.
- SHA-256: `30cf81c360cb28f45ee97234779689bdcdd7ec3aa8fa148645a4b015771be6c6`.

### Taron

- File: [Taron-E929A20E-9E53-4C09-81F0-E2D3AED1E626.forces](../../tests/fixtures/real/Taron-E929A20E-9E53-4C09-81F0-E2D3AED1E626.forces)
- Size: 782329 bytes.
- SHA-256: `cfa03821140aaa76c52e1bb69905db96a775a5d6772741b5d3a90f48a4254564`.

### Voltron Nevera

- File: [VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces](../../tests/fixtures/real/VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces)
- Size: 862820 bytes.
- SHA-256: `f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04`.

## Current test coverage

`tests/test_project.py` verifies the exact four-file inventory and checks each
recording independently for its pinned byte length and SHA-256. Parametrized test
IDs identify Kraken, Manta, Taron and VoltronNevera in pytest and VS Code discovery.
The tests read bytes only; they do not parse or rewrite recordings.

Run the focused checks from the repository root:

```powershell
uv run pytest tests/test_project.py
```

GUI, bootstrap-settings, lint and static typing tests do not consume recording
samples and therefore need no per-recording variants. The CI pytest step
collects all fixture cases automatically. Recordings remain excluded from CSpell
and formatting checks so their original contents are not treated as source code.

## Planned importer and analysis coverage

M2 must validate lossless ingestion of all four recordings while preserving
unknown fields and original bytes. M3 must cross-check coordinates, timing,
calibration, filtering and GPS sentinels against the original Ride Forces app.
The byte-integrity checks do not establish those scientific or schema contracts.
M2/M3 functionality and tests remain planned; none is implemented by this update.
