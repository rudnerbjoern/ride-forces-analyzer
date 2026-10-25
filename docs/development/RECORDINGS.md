# Real recording fixtures

<!-- cspell:words zforces -->

## Authorization and use

Copyright © 2026 Björn Rudner. All owner-supplied test and reference data in this
project are licensed under **CC BY-SA 4.0**, including complete recordings and
app exports in any format. This includes
embedded GPS positions, timestamps, sensor values, metadata and unknown fields.
The owner approved this license for all test and reference data on 2026-10-21. The
[license scope and attribution](../../tests/fixtures/real/README.md) identify the
licensor and reuse conditions; the [complete legal text](../../tests/fixtures/real/LICENSE-CC-BY-SA-4.0.txt)
is supplied alongside the files. Recipients may share and adapt the recordings,
including commercially, with attribution, a license link and change indications.
Shared adaptations must use the same or an officially compatible license under
the ShareAlike terms.
Program code and documentation images retain their separate licenses.

The owner authorizes using and publishing these complete data for project testing,
development and reference comparisons. This data authorization does not authorize
Git operations. Preserve original reference files byte-for-byte, including unknown
fields and metadata; neither Git nor editor tooling may normalize or reformat them.

## Fixture catalog

The sizes and SHA-256 digests below were computed by reading the original bytes.
Recording identities are pinned in `tests/support/recordings.py`; changes require
updating the tests and this catalog together.

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

- File: [Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.forces](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.forces)
- Size: 783028 bytes.
- SHA-256: `1d06e636b0cd26c7634503bf3f5f93e1906791ce47028c129af1c1828c7b268c`.
- 9638 acceleration and gravity samples and 145 GPS points.
- Owner-confirmed [Manta HUD demo](https://youtu.be/JGcNPKoKU1Q): row 3, seat 3,
  created from this reference recording.

### Taron

- File: [Taron-E929A20E-9E53-4C09-81F0-E2D3AED1E626.forces](../../tests/fixtures/real/Taron-E929A20E-9E53-4C09-81F0-E2D3AED1E626.forces)
- Size: 782329 bytes.
- SHA-256: `cfa03821140aaa76c52e1bb69905db96a775a5d6772741b5d3a90f48a4254564`.

### Typhoon

- File: [Typhoon-BBEC0F05-692B-4CED-B5C7-EEB8C7BCDBF1.forces](../../tests/fixtures/rfdb/Typhoon-BBEC0F05-692B-4CED-B5C7-EEB8C7BCDBF1.forces)
- Size: 365978 bytes.
- SHA-256: `c6c561c1156c1197462159775866b43ce69b1ed44f7bb39bced8a37e4c2122eb`.
- Owner-created recording downloaded from RFDB; inclusion as complete test and
  reference data authorized on 2026-10-23 under the common CC BY-SA 4.0 terms.
- Unversioned JSON with calibration vectors, 9242 acceleration samples and an
  explicit 50 Hz sample rate; gravity and GPS sequences are absent.

### Voltron Nevera

- File: [VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces](../../tests/fixtures/real/VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces)
- Size: 862820 bytes.
- SHA-256: `f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04`.

## Source-app CSV reference

- File: [Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.csv](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.csv).
- Owner-supplied Ride Forces app export, covered by the common CC BY-SA 4.0 grant.
- Size: 248028 bytes.
- SHA-256: `99cb644c8e5fb6cb6d4a0bd4c231f198215ff6f8bb90dc58f5d1baa20a79107b`.
- Preserve original bytes, including CRLF line endings. The recording ID matches
  the Manta `.forces` fixture; selected source-app comparisons are documented in
  [comparison evidence](../validation/APP_REFERENCE.md#manta-replay-reference).

## Source-app JSON reference

- File: [Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.json](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.json).
- Owner-supplied Ride Forces app export, covered by the common CC BY-SA 4.0 grant.
- Size: 179174 bytes.
- SHA-256: `f76e04a71a339ec619b6b764847510f8a8c1a5d4989d3d447fb61f3b275d7379`.
- Preserve original bytes. This export shares its recording ID with the Manta
  `.forces`, CSV and zforces references; sample correspondence is not established
  by the identifier alone.

## Source-app zforces reference

- File: [Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.zforces](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.zforces).
- Owner-supplied Ride Forces app export, covered by the common CC BY-SA 4.0 grant.
- Size: 91361 bytes.
- SHA-256: `005ce708ec946bcf4dbe0163fc2fb23c629b65c1ed11706000c130855c4ba1e5`.
- Preserve original bytes. Raw-DEFLATE expands to 783028 bytes of schema 2.2.0 JSON.
  All JSON fields and values match the Manta `.forces` reference, including 9638
  acceleration/gravity samples and 145 GPS entries; object-member order differs.

## Validation and scientific limits

`tests/recordings/test_integrity.py` verifies the complete recording inventory and the
original byte lengths/SHA-256 pinned in `tests/support/recordings.py`.
`tests/recordings/test_inventory.py` compares
the complete recursive snapshots for [app exports](../../tests/fixtures/schema-inventory.json)
and [RFDB exports](../../tests/fixtures/rfdb-schema-inventory.json);
see [source observations](../architecture/08_concepts.md#source-ownership-and-validation).
The same complete inventory pass verifies every fixture's pinned identity and
unchanged bytes/modification time; synthetic cases separately exercise traversal
and invalid-input behavior.

```powershell
uv run --locked pytest tests/recordings/test_inventory.py tests/recordings/test_integrity.py
```

The five schema 2.2.0 recordings form the existing [importer](IMPORT_SERVICE.md)
reference corpus; the unversioned RFDB recording is cataloged separately under
`tests/fixtures/rfdb/`. The
[import contract](../architecture/08_concepts.md#source-ownership-and-validation)
summarizes full motion/GPS/metadata preservation.
Analysis model/device tests preserve source bytes and exercise unavailable Watch
capabilities. These checks do not qualify units, axes, calibration, timing,
filtering, GPS sentinels or source-app equivalence. The separate
[source comparisons](../validation/APP_REFERENCE.md) define qualified display
contracts and remaining physical uncertainties.
Recordings are excluded from spelling, formatting and normalization.
