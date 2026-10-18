# Real recording fixtures

## Authorization and use

The owner expressly authorizes using and publishing all four complete Ride Forces
recordings below in this project for testing and development, including all
embedded data such as authentic GPS positions and metadata. Manta was authorized
with the original M1 fixture; Kraken, Taron and Voltron Nevera were added and
expressly authorized on 2026-10-13.

This publication authorization covers the original quartet. The owner additionally
supplied Iron Gwazi on 2026-10-13 for inspection and confirmed
its Apple Watch availability profile. The owner subsequently explicitly authorized
committing and pushing the complete fifth fixture on
2026-10-13. PR creation and merge require separate authorization.
Additional recordings require their
own authorization before inclusion or publication. Keep every `.forces` file
read-only and preserve its original bytes, unknown fields and metadata. Neither
Git nor editor tooling may normalize or reformat these recordings.

## Fixture catalog

The sizes and SHA-256 digests below were computed by reading the original bytes.
They are pinned in `tests/test_project.py`; intentionally replacing a recording
requires reviewing its authorization, tests and this catalog together.

### Iron Gwazi

- File: [IronGwazi-E1A4DA01-0231-4EF6-9A9A-F58C3AB020EB.forces](../../tests/fixtures/real/IronGwazi-E1A4DA01-0231-4EF6-9A9A-F58C3AB020EB.forces)
- Size: 346781 bytes.
- SHA-256: `cfea878d208ca082c41562084c9d5b3635c4ac1de6e6c583cee17e53d0becbcb`.
- Device: Apple Watch; acceleration is present, gravity/GPS are absent.

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

## Validation and scientific limits

`tests/test_project.py` verifies the exact five-file inventory and independently
pins each original byte length/SHA-256. `tests/test_fixture_inventory.py` compares
the complete [recursive snapshot](../../tests/fixtures/schema-inventory.json);
see [format observations](../requirements/FORMAT-ANALYSIS.md).

```powershell
uv run --locked pytest tests/test_fixture_inventory.py tests/test_project.py
```

The [public importer](IMPORT_SERVICE.md) losslessly imports all five originals;
[M2 acceptance](../validation/M2.md) records full motion/GPS/metadata coverage.
Analysis model/device tests preserve source bytes and exercise unavailable Watch
capabilities. These checks do not qualify units, axes, calibration, timing,
filtering, GPS sentinels or source-app equivalence. The separate
[source comparisons](../validation/APP_REFERENCE.md) define qualified display
contracts and remaining physical uncertainties.
Recordings are excluded from spelling, formatting and normalization.
