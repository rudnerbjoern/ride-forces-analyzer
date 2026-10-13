"""Test-only recursive observations; this is not the production forces decoder."""

import argparse
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re
from typing import NotRequired, TypedDict, cast

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "tests" / "fixtures" / "real"
DECIMAL_STRING = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


class PathSummary(TypedDict):
    types: dict[str, int]
    members: NotRequired[dict[str, int]]
    array_lengths: NotRequired[dict[str, int]]
    number_encodings: NotRequired[dict[str, int]]
    negative_numbers: NotRequired[int]
    string_length_min: NotRequired[int]
    string_length_max: NotRequired[int]
    finite_decimal_strings: NotRequired[int]


class FixtureSummary(TypedDict):
    byte_count: int
    sha256: str
    node_count: int
    max_container_depth: int
    max_number_token_length: int
    paths: dict[str, PathSummary]


class FieldPresence(TypedDict):
    present_in: list[str]
    absent_in: list[str]


class Snapshot(TypedDict):
    snapshot_version: int
    fixtures: dict[str, FixtureSummary]
    top_level_presence: dict[str, FieldPresence]


@dataclass
class Observations:
    types: Counter[str] = field(default_factory=Counter[str])
    members: Counter[str] = field(default_factory=Counter[str])
    lengths: Counter[int] = field(default_factory=Counter[int])
    numbers: Counter[str] = field(default_factory=Counter[str])
    negative_numbers: int = 0
    string_lengths: list[int] = field(default_factory=list[int])
    finite_decimal_strings: int = 0

    def summary(self) -> PathSummary:
        result: PathSummary = {"types": dict(sorted(self.types.items()))}
        if "object" in self.types:
            result["members"] = dict(sorted(self.members.items()))
        if "array" in self.types:
            result["array_lengths"] = {str(n): count for n, count in sorted(self.lengths.items())}
        if self.numbers:
            result["number_encodings"] = dict(sorted(self.numbers.items()))
            result["negative_numbers"] = self.negative_numbers
        if self.string_lengths:
            result["string_length_min"] = min(self.string_lengths)
            result["string_length_max"] = max(self.string_lengths)
            result["finite_decimal_strings"] = self.finite_decimal_strings
        return result


def inspect_bytes(raw: bytes) -> FixtureSummary:
    """Visit every value, retaining type/presence counts without printing GPS values."""
    max_token_length = 0

    def integer(token: str) -> int:
        nonlocal max_token_length
        max_token_length = max(max_token_length, len(token))
        return int(token)

    def decimal(token: str) -> float:
        nonlocal max_token_length
        max_token_length = max(max_token_length, len(token))
        value = float(token)
        if not isfinite(value):
            raise ValueError("Non-finite number in inventory input")
        return value

    def constant(_token: str) -> JsonValue:
        raise ValueError("Non-JSON constant in inventory input")

    def members(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate object member in inventory input")
            result[key] = value
        return result

    tree = cast(
        JsonValue,
        json.loads(
            raw.decode("utf-8"),
            parse_int=integer,
            parse_float=decimal,
            parse_constant=constant,
            object_pairs_hook=members,
        ),
    )
    paths: dict[str, Observations] = {}
    node_count = 0
    max_depth = 0

    def visit(value: JsonValue, path: str, depth: int) -> None:
        nonlocal node_count, max_depth
        node_count += 1
        observations = paths.setdefault(path, Observations())
        if isinstance(value, dict):
            observations.types["object"] += 1
            observations.members.update(value.keys())
            max_depth = max(max_depth, depth + 1)
            for key, child in value.items():
                visit(child, path + "[" + json.dumps(key, ensure_ascii=False) + "]", depth + 1)
        elif isinstance(value, list):
            observations.types["array"] += 1
            observations.lengths[len(value)] += 1
            max_depth = max(max_depth, depth + 1)
            for child in value:
                visit(child, path + "[*]", depth + 1)
        elif isinstance(value, str):
            observations.types["string"] += 1
            observations.string_lengths.append(len(value))
            if DECIMAL_STRING.fullmatch(value) and Decimal(value).is_finite():
                observations.finite_decimal_strings += 1
        elif isinstance(value, bool):
            observations.types["boolean"] += 1
        elif value is None:
            observations.types["null"] += 1
        else:
            observations.types["number"] += 1
            observations.numbers[
                "integer" if isinstance(value, int) else "decimal_or_exponent"
            ] += 1
            observations.negative_numbers += int(value < 0)

    visit(tree, "$", 0)
    return {
        "byte_count": len(raw),
        "sha256": sha256(raw).hexdigest(),
        "node_count": node_count,
        "max_container_depth": max_depth,
        "max_number_token_length": max_token_length,
        "paths": {path: observations.summary() for path, observations in sorted(paths.items())},
    }


def inventory(directory: Path = REAL) -> Snapshot:
    fixtures = {
        path.name: inspect_bytes(path.read_bytes()) for path in sorted(directory.glob("*.forces"))
    }
    field_names = {
        key for fixture in fixtures.values() for key in fixture["paths"]["$"].get("members", {})
    }
    fields = sorted(field_names)
    presence: dict[str, FieldPresence] = {}
    for key in fields:
        presence[key] = {
            "present_in": [
                name
                for name, fixture in fixtures.items()
                if key in fixture["paths"]["$"].get("members", {})
            ],
            "absent_in": [
                name
                for name, fixture in fixtures.items()
                if key not in fixture["paths"]["$"].get("members", {})
            ],
        }
    return {"snapshot_version": 1, "fixtures": fixtures, "top_level_presence": presence}


def snapshot_bytes(snapshot: Snapshot) -> bytes:
    text = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = cast(Path, parser.parse_args().output).resolve()
    if not output.is_relative_to(ROOT / ".tmp"):
        parser.error("Inventory output must be under the repository .tmp directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(snapshot_bytes(inventory()))
    print("Wrote recursive fixture observations; no original recording was written.")
