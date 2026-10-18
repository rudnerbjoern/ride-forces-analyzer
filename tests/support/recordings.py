"""Paths and pinned identities of the five authorized original recordings."""

from pathlib import Path

REAL_FIXTURE_DIRECTORY = Path(__file__).resolve().parents[1] / "fixtures" / "real"
# Owner-supplied recordings; expected sizes and digests pin the original bytes.
REAL_FIXTURES: dict[str, tuple[int, str]] = {
    "IronGwazi-E1A4DA01-0231-4EF6-9A9A-F58C3AB020EB.forces": (
        346781,
        "cfea878d208ca082c41562084c9d5b3635c4ac1de6e6c583cee17e53d0becbcb",
    ),
    "Kraken-1537D9CF-418B-4F13-AA1A-F303F9DE2311.forces": (
        837779,
        "f418e8323beeba1ab81da93705b18b0baee3622c2b702ef34b72cd550d45984d",
    ),
    "Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces": (
        801293,
        "30cf81c360cb28f45ee97234779689bdcdd7ec3aa8fa148645a4b015771be6c6",
    ),
    "Taron-E929A20E-9E53-4C09-81F0-E2D3AED1E626.forces": (
        782329,
        "cfa03821140aaa76c52e1bb69905db96a775a5d6772741b5d3a90f48a4254564",
    ),
    "VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces": (
        862820,
        "f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04",
    ),
}
