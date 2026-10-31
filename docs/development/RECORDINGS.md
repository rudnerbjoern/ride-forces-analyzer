# Real recording fixtures

## Authorization and use

The [central owner grant](../../ASSET_LICENSES.md) defines the license scope,
author, attribution and reuse conditions for all supplied recordings and original
app exports. The complete [legal text](../../tests/fixtures/real/LICENSE-CC-BY-SA-4.0.txt)
is retained with the fixtures for redistribution.

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

## Force extrema with 11-sample smoothing

Calculated from the six pinned originals using `source_app_configuration()` and
`calculate_extrema()`: stored calibration directions, centered 11-sample mean,
shortened and renormalized windows at recording edges. All recordings use 50 Hz;
the smoothing support is five samples (0.10 s) on either side. No local calibration
or marker overrides are applied. Values are in g, rounded to three decimal places.
Each pair is **minimum / maximum**; the maximum magnitude is the larger absolute value.

The reference interval is bounded by the original start/end markers, inclusively.
Samples outside this interval can contain handling or body movements unrelated to
the ride and are excluded from the extrema search. Smoothing retains the full
recording history rather than restarting at the markers.

| Recording      | Included samples (inclusive) | Vertical min / max | Longitudinal min / max | Lateral min / max |
| -------------- | ---------------------------- | ------------------ | ---------------------- | ----------------- |
| Iron Gwazi     | 1720–8179                    | -1.334 / +3.784    | -1.274 / +1.090        | -1.217 / +1.105   |
| Kraken         | 913–9138                     | -0.220 / +4.077    | -1.093 / +0.448        | -0.712 / +0.422   |
| Manta          | 2750–9637                    | -3.557 / +2.638    | -0.681 / +0.715        | -0.937 / +1.129   |
| Taron          | 2284–6639                    | -0.626 / +4.346    | -0.918 / +1.082        | -0.688 / +1.278   |
| Typhoon        | 4109–7957                    | -1.030 / +4.982    | -1.053 / +1.054        | -0.929 / +1.543   |
| Voltron Nevera | 1571–10374                   | -1.598 / +4.365    | -1.208 / +1.073        | -1.262 / +0.921   |

Longitudinal means acceleration/braking; lateral means right/left. Signs retain
the stored source-axis convention. Manta is **Flying**; the other references are
**Seated**. In particular, Manta's negative vertical peak must not be interpreted
as the same rider loading as a negative Seated value. These are prepared values
under the owner-adopted source-app policy, not independent physical qualification;
see the [source comparisons](../validation/APP_REFERENCE.md).

## Source-app CSV reference

- File: [Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.csv](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.csv).
- Owner-supplied Ride Forces app export covered by the [central owner grant](../../ASSET_LICENSES.md).
- Size: 248028 bytes.
- SHA-256: `99cb644c8e5fb6cb6d4a0bd4c231f198215ff6f8bb90dc58f5d1baa20a79107b`.
- Preserve original bytes, including CRLF line endings. The recording ID matches
  the Manta `.forces` fixture; selected source-app comparisons are documented in
  [comparison evidence](../validation/APP_REFERENCE.md#manta-replay-reference).

## Source-app JSON reference

- File: [Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.json](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.json).
- Owner-supplied Ride Forces app export covered by the [central owner grant](../../ASSET_LICENSES.md).
- Size: 179174 bytes.
- SHA-256: `f76e04a71a339ec619b6b764847510f8a8c1a5d4989d3d447fb61f3b275d7379`.
- Preserve original bytes. This export shares its recording ID with the Manta
  `.forces`, CSV and zforces references; sample correspondence is not established
  by the identifier alone.

## Source-app zforces reference

- File: [Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.zforces](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.zforces).
- Owner-supplied Ride Forces app export covered by the [central owner grant](../../ASSET_LICENSES.md).
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
