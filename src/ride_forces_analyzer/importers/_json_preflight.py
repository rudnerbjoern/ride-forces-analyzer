"""Iterative grammar/resource preflight before allocating a full JSON tree.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words codepoint bfnrt

from dataclasses import dataclass, field
from decimal import InvalidOperation
import json
import re
from typing import cast

from ride_forces_analyzer.domain import SourceNumber

from .diagnostics import ImportDiagnostic, Severity, json_pointer
from .limits import ImportLimits

type JsonPath = tuple[str | int, ...]
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_HEX = frozenset("0123456789abcdefABCDEF")
_SPACE = frozenset(" \t\r\n")


class DecodeProblem(Exception):
    """Decode problem contract and owned data.

    Attributes:
        diagnostic: Structured diagnostic with code and source location.
    """

    def __init__(self, code: str, path: JsonPath, message: str) -> None:
        """Initialize decode problem and its owned state.

        Args:
            code: Stable diagnostic code used to select its localized explanation.
            path: Filesystem path read or written by this operation.
            message: Text or diagnostic message to present or validate.

        Returns:
            None.
        """
        self.diagnostic = ImportDiagnostic(code, Severity.ERROR, json_pointer(*path), message)
        super().__init__(message)


def _limit(name: str, path: JsonPath) -> None:
    raise DecodeProblem("RESOURCE_LIMIT_EXCEEDED", path, f"Resource budget exceeded: {name}")


def _syntax(path: JsonPath) -> None:
    raise DecodeProblem("INVALID_JSON", path, "Invalid JSON syntax")


def _string_end(text: str, start: int, path: JsonPath, limits: ImportLimits) -> int:
    index = start + 1
    characters = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            return index + 1
        if ord(char) < 32:
            _syntax(path)
        if char == "\\":
            index += 1
            if index >= len(text):
                _syntax(path)
            escaped = text[index]
            if escaped == "u":
                digits = text[index + 1 : index + 5]
                if len(digits) != 4 or any(digit not in _HEX for digit in digits):
                    _syntax(path)
                codepoint = int(digits, 16)
                index += 4
                # JSON combines a valid escaped UTF-16 surrogate pair into one character.
                if 0xD800 <= codepoint <= 0xDBFF and text[index + 1 : index + 3] == "\\u":
                    low = text[index + 3 : index + 7]
                    if len(low) == 4 and all(digit in _HEX for digit in low):
                        if 0xDC00 <= int(low, 16) <= 0xDFFF:
                            index += 6
            elif escaped not in '"\\/bfnrt':
                _syntax(path)
        characters += 1
        if characters > limits.max_string_length:
            _limit("max_string_length", path)
        index += 1
    _syntax(path)
    raise AssertionError("unreachable")


@dataclass(slots=True)
class _Frame:
    """Frame contract and owned data.

    Attributes:
        kind: Discriminator identifying the represented variant.
        path: Filesystem path read or written by this operation.
        state: Declared capability, request or parsing state for this object.
        count: Number of retained items or samples represented by this object.
        key: Lookup or presentation key used by the operation.
        keys: Object keys encountered in the current parsing frame.
    """

    kind: str
    path: JsonPath
    state: str
    count: int = 0
    key: str = ""
    keys: set[str] = field(default_factory=set[str])


def preflight(text: str, limits: ImportLimits) -> None:
    """Check all nodes, including unknown extensions, using a bounded explicit stack.

    Args:
        text: Presentation text or source template to bind.
        limits: Resource limits applied to the operation.

    Returns:
        None.

    Raises:
        DecodeProblem: DUPLICATE_JSON_KEY. NON_JSON_NUMBER. INVALID_JSON_NUMBER.
        AssertionError: unreachable.
    """
    stack: list[_Frame] = []
    index = 0
    nodes = 0
    root_started = False
    while True:
        while index < len(text) and text[index] in _SPACE:
            index += 1
        if not stack and root_started:
            if index != len(text):
                _syntax(())
            return
        path: JsonPath = ()
        if stack:
            frame = stack[-1]
            path = frame.path
            char = text[index] if index < len(text) else ""
            if frame.kind == "object" and frame.state in ("first_key", "key"):
                if char == "}" and frame.state == "first_key":
                    stack.pop()
                    index += 1
                    continue
                if char != '"':
                    _syntax(path)
                frame.count += 1
                if frame.count > limits.max_object_members:
                    _limit("max_object_members", path)
                end = _string_end(text, index, path, limits)
                frame.key = cast(str, json.loads(text[index:end]))
                child_path = (*path, frame.key)
                if frame.key in frame.keys:
                    raise DecodeProblem("DUPLICATE_JSON_KEY", child_path, "Duplicate object member")
                frame.keys.add(frame.key)
                frame.state = "colon"
                index = end
                continue
            if frame.state == "colon":
                if char != ":":
                    _syntax((*path, frame.key))
                frame.state = "value"
                index += 1
                continue
            if frame.state == "after_value":
                close = "}" if frame.kind == "object" else "]"
                if char == close:
                    stack.pop()
                elif char == ",":
                    frame.state = "key" if frame.kind == "object" else "value"
                else:
                    _syntax(path)
                index += 1
                continue
            if frame.kind == "array":
                if char == "]" and frame.state == "first_value":
                    stack.pop()
                    index += 1
                    continue
                if frame.count >= limits.max_sequence_length:
                    _limit("max_sequence_length", path)
                path = (*path, frame.count)
                frame.count += 1
            else:
                path = (*path, frame.key)
            frame.state = "after_value"
        root_started = True
        nodes += 1
        if nodes > limits.max_nodes:
            _limit("max_nodes", path)
        if index >= len(text):
            _syntax(path)
        char = text[index]
        if char in "{[":
            if len(stack) + 1 > limits.max_depth:
                _limit("max_depth", path)
            kind = "object" if char == "{" else "array"
            state = "first_key" if kind == "object" else "first_value"
            stack.append(_Frame(kind, path, state))
            index += 1
        elif char == '"':
            index = _string_end(text, index, path, limits)
        elif char in "-0123456789":
            if text.startswith("-Infinity", index):
                raise DecodeProblem("NON_JSON_NUMBER", path, "Non-JSON numeric constant")
            match = _NUMBER.match(text, index)
            if match is None:
                _syntax(path)
                raise AssertionError("unreachable")
            if match.end() - index > limits.max_number_length:
                _limit("max_number_length", path)
            try:
                SourceNumber(match.group())
            except ValueError, InvalidOperation:
                raise DecodeProblem(
                    "INVALID_JSON_NUMBER",
                    path,
                    "Number cannot be represented exactly",
                ) from None
            index = match.end()
        elif text.startswith(("NaN", "Infinity"), index):
            raise DecodeProblem("NON_JSON_NUMBER", path, "Non-JSON numeric constant")
        else:
            for literal in ("true", "false", "null"):
                if text.startswith(literal, index):
                    index += len(literal)
                    break
            else:
                _syntax(path)
