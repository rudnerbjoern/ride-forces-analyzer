"""Create one readable dependency inventory with deduplicated upstream notices.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words ufeff

from dataclasses import dataclass
from pathlib import Path
import re

BUNDLE_NAME = "THIRD-PARTY-LICENSES.txt"


@dataclass(frozen=True)
class _Notice:
    """Original source and attribution referencing shared license terms.

    Attributes:
        source: Original upstream notice path or metadata field.
        attribution: Unmodified prefix kept with the owning component.
        text_key: Whitespace-normalized identity of the shared body.
    """

    source: str
    attribution: str
    text_key: str


@dataclass(frozen=True)
class _Component:
    """Installed library or bundled material with its notice associations.

    Attributes:
        name: Upstream component name.
        version: Installed or bundled version.
        license: Original license declaration or collection label.
        notices: Source-specific attributions and shared-text references.
    """

    name: str
    version: str
    license: str
    notices: tuple[_Notice, ...]


class LicenseBundle:
    """Associate libraries and attributions with shared, original license texts.

    Only whitespace-equivalent bodies are merged. Different conditions, exceptions
    and bundled-component notices retain separate bodies within their type section.
    Copyright prefixes of short permissive licenses remain beside each component.

    Attributes:
        components: Libraries and their original notice-source associations.
        texts: Unique bodies keyed by their whitespace-normalized text.
        kinds: Type labels for the shared text bodies.
    """

    def __init__(self) -> None:
        """Create an empty notice collection."""
        self.components: list[_Component] = []
        self.texts: dict[str, str] = {}
        self.kinds: dict[str, str] = {}

    def add(
        self,
        name: str,
        version: str,
        license_name: str,
        sources: list[tuple[str, str, str]],
    ) -> None:
        """Add component notices without losing attribution or license variants.

        Args:
            name: Library or bundled-material name.
            version: Exact installed or bundled version.
            license_name: Upstream license declaration, or an inventory label.
            sources: Original source name, license type and complete notice text.

        Raises:
            ValueError: A component has no readable notice text.
        """
        notices: list[_Notice] = []
        for source, kind, original in sources:
            text = original.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff\n ")
            if not text:
                continue
            # Separate attribution only at recognized permissive-license terms.
            # This preserves the entire original prefix and body, including exceptions.
            terms = re.search(
                r"(?mi)^(?:Permission\s+is\s+hereby\s+granted,\s+free\s+of\s+charge|Redistribution\s+and\s+use\s+in\s+source\s+and\s+binary\s+forms|Permission\s+to\s+use,\s+copy,\s+modify,\s+and\s+distribute)",
                text,
            )
            if terms and re.search(
                r"(?i)\b(?:permission|redistribution|license agreement|terms and conditions)\b",
                text[: terms.start()],
            ):
                terms = None
            attribution = text[: terms.start()].strip() if terms else ""
            body = text[terms.start() :] if terms else text
            key = " ".join(body.split())
            if key not in self.texts:
                self.texts[key] = body
                self.kinds[key] = kind
            elif kind != "Additional component notices":
                labels = set(self.kinds[key].split(" / ")) - {"Additional component notices"}
                self.kinds[key] = " / ".join(sorted(labels | {kind}))
            notices.append(_Notice(source, attribution, key))
        if not notices:
            raise ValueError(f"Missing license notices for {name}")
        self.components.append(_Component(name, version, license_name, tuple(notices)))

    def write(self, destination: Path) -> None:
        """Write one UTF-8 inventory, attribution list and shared license collection.

        Args:
            destination: Consolidated notice file to create.

        Raises:
            OSError: The destination cannot be created or written.
        """
        identifiers = {key: f"L{index:03d}" for index, key in enumerate(self.texts, 1)}
        lines = [
            "THIRD-PARTY LICENSES AND NOTICES",
            "",
            "Library inventory and original copyright/attribution notices follow.",
            "License text references resolve within this file; identical terms appear once.",
            "Different terms and exceptions are retained, even within the same license type.",
            "",
            "LIBRARIES AND ATTRIBUTIONS",
            "",
        ]
        for component in self.components:
            lines += [f"{component.name} {component.version} — {component.license}"]
            for notice in component.notices:
                lines.append(f"  [{identifiers[notice.text_key]}] {notice.source}")
                if notice.attribution:
                    lines.append(notice.attribution)
            lines.append("")
        lines += ["LICENSE TEXTS AND ADDITIONAL NOTICES", ""]
        for kind in sorted(set(self.kinds.values()), key=str.casefold):
            lines += [f"===== {kind} =====", ""]
            for key, text in self.texts.items():
                if self.kinds[key] == kind:
                    lines += [f"[{identifiers[key]}]", text, ""]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("\n".join(lines), encoding="utf-8")


def read_notice(path: Path) -> str:
    """Decode an upstream notice without replacing undecodable bytes.

    Args:
        path: Original notice file.

    Returns:
        UTF-8 text, or lossless Latin-1 text for legacy upstream notices.

    Raises:
        OSError: The original notice file cannot be read.
    """
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return text.replace("\r\n", "\n").replace("\r", "\n")
