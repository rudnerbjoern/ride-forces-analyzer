"""Shared Python/TypeScript control messages and strict wire-boundary regressions."""

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import get_args

import pytest
from pydantic import ValidationError

from ride_forces_analyzer.runtime.control_contract import (
    ActionName,
    PROTOCOL_VERSION,
    Command,
    ErrorCode,
    Failure,
    MarkerState,
    parse_command,
    parse_server_message,
    Result,
    StateEvent,
    UnavailableReason,
)
from ride_forces_analyzer.runtime.instance import OpenRequest

FIXTURE = Path(__file__).parents[2] / "tests/fixtures/stream_deck_protocol.json"
EXAMPLES = json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_protocol_version_requires_explicit_owner_approval() -> None:
    message = "Protocol version 3 is owner-approved; changing it requires explicit owner approval."
    assert PROTOCOL_VERSION == 3, message
    source = (FIXTURE.parents[2] / "plugins/stream-deck/src/protocol.ts").read_text(
        encoding="utf-8",
    )
    assert re.search(r"^export const PROTOCOL_VERSION = 3;$", source, re.MULTILINE), message


def test_error_and_reason_codes_use_dotted_names() -> None:
    for code in (*get_args(ErrorCode), *get_args(UnavailableReason)):
        assert re.fullmatch(r"[a-z]+(?:\.[a-z]+)+", code), code


@pytest.mark.parametrize("action", EXAMPLES["actions"], ids=lambda value: value["name"])
def test_all_agreed_actions_round_trip(action: dict[str, object]) -> None:
    payload: dict[str, object] = {
        "version": PROTOCOL_VERSION,
        "type": "command",
        "id": "request-1",
        "target": EXAMPLES["target"],
        "action": action,
    }
    command = parse_command(json.dumps(payload))
    assert json.loads(command.model_dump_json()) == payload
    assert command.target.window_id == "explorer-1"
    assert command.target.generation == 3


def test_shared_examples_cover_every_action_and_server_envelope() -> None:
    assert {action["name"] for action in EXAMPLES["actions"]} == set(get_args(ActionName))
    messages = [parse_server_message(json.dumps(value)) for value in EXAMPLES["messages"]]
    assert {type(message) for message in messages} == {StateEvent, Result, Failure}
    for original, parsed in zip(EXAMPLES["messages"], messages, strict=True):
        assert json.loads(parsed.model_dump_json()) == original


def test_filter_values_preserve_long_unicode_text_without_identifier_limits() -> None:
    value = "  Park <&\"'> \\ /\t\n東京 e\u0301 👩‍🚀 " + "Ž🎢" * 800 + "  "
    action = {"name": "library.filter.set", "filter": "park", "value": value}
    command = {
        "version": PROTOCOL_VERSION,
        "type": "command",
        "id": "filter",
        "target": EXAMPLES["target"],
        "action": action,
    }
    state = deepcopy(EXAMPLES["messages"][0])
    state["library"]["park_filter"]["options"].append({"value": value, "label": value})
    state["library"]["park_filter"]["value"] = value
    for ascii_only in (False, True):
        parsed = parse_command(json.dumps(command, ensure_ascii=ascii_only))
        assert json.loads(parsed.model_dump_json())["action"] == action
        feedback = parse_server_message(json.dumps(state, ensure_ascii=ascii_only))
        assert json.loads(feedback.model_dump_json()) == state


@pytest.mark.parametrize(
    "choice",
    [
        {"value": "absent", "options": []},
        {"value": "absent", "options": [{"value": None, "label": "All"}]},
        {"value": None, "options": [{"value": None, "label": "All"}] * 2},
        {"value": True, "options": [{"value": True, "label": "Invalid"}]},
        {"value": None, "options": [{"value": None, "label": 1}]},
        {"value": None, "options": [{"value": None, "label": "All", "index": 0}]},
    ],
)
def test_invalid_filter_feedback_is_rejected(choice: dict[str, object]) -> None:
    state = deepcopy(EXAMPLES["messages"][0])
    state["library"]["park_filter"] = choice
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(state))


@pytest.mark.parametrize("version", [True, "3", 0, 1, 2, 4, 5, 6, 7])
def test_incompatible_and_coerced_versions_are_rejected(version: object) -> None:
    with pytest.raises(ValidationError):
        parse_command(
            json.dumps(
                {
                    "version": version,
                    "type": "command",
                    "id": "request-1",
                    "target": EXAMPLES["target"],
                    "action": {"name": "library.import"},
                },
            ),
        )
    state = deepcopy(EXAMPLES["messages"][0])
    state["version"] = version
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(state))


@pytest.mark.parametrize(
    "action",
    [
        {"name": "unknown"},
        {"name": "library.open.same", "new_window": True},
        {"name": "library.move", "direction": 10},
        {"name": "library.move", "direction": True},
        {"name": "position.step", "steps": 2},
        {"name": "position.step", "steps": True},
        {"name": "curve.set", "curve": "combined", "enabled": "yes"},
        {"name": "marker.preview", "marker": "missing", "steps": 1},
        {"name": "marker.apply"},
        {"name": "selection.step", "boundary": "gravity", "steps": 1},
        {"name": "selection.step", "boundary": "end", "steps": True},
        {"name": "library.filter.set", "filter": "ride", "value": None},
        {"name": "library.filter.set", "filter": "park", "value": 12},
        {"name": "library.filter.set", "filter": "park", "value": True},
        {"name": "library.filter.set", "filter": "park", "value": []},
        {"name": "library.filter.set", "filter": "park"},
    ],
)
def test_unknown_or_invalid_action_arguments_are_rejected(action: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        parse_command(
            json.dumps(
                {
                    "version": PROTOCOL_VERSION,
                    "type": "command",
                    "id": "request-1",
                    "target": EXAMPLES["target"],
                    "action": action,
                },
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sequence", -1),
        (
            "selection",
            {
                "start": {"sample": 20, "time_seconds": 1.0, "label": "a"},
                "end": {"sample": 10, "time_seconds": 0.5, "label": "b"},
            },
        ),
        ("availability", {"available": False}),
        ("availability", {"available": 1}),
        ("playback", {"playing": False, "speed": True, "position": None, "last_sample": None}),
        ("view", {"start_seconds": 0.0, "end_seconds": 1.0, "smoothing_window": 2}),
        ("view", {"start_seconds": float("nan"), "end_seconds": 1.0, "smoothing_window": 11}),
    ],
)
def test_invalid_feedback_values_are_rejected(field: str, value: object) -> None:
    state = deepcopy(EXAMPLES["messages"][0])
    state[field] = value
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(state))


@pytest.mark.parametrize("status", ["applied", "preview", "pending", "failed"])
def test_marker_feedback_keeps_applied_and_proposed_values_separate(status: str) -> None:
    payload = deepcopy(EXAMPLES["messages"][0]["markers"][1])
    payload["status"] = status
    if status == "applied":
        payload["preview"] = None
    payload["request_id"] = "apply-1" if status in {"pending", "failed"} else None
    payload["error"] = "analysis.failed" if status == "failed" else None
    marker = MarkerState.model_validate_json(json.dumps(payload))
    assert marker.applied is not None and marker.applied.sample == 50
    if status == "applied":
        assert marker.preview is None
    else:
        assert marker.preview is not None and marker.preview.sample == 51
    assert marker.status == status


@pytest.mark.parametrize(
    ("status", "request_id", "error"),
    [
        ("applied", None, None),
        ("pending", None, None),
        ("failed", "apply-1", None),
        ("preview", None, "analysis.failed"),
    ],
)
def test_inconsistent_marker_application_status_is_rejected(
    status: str,
    request_id: str | None,
    error: str | None,
) -> None:
    payload = deepcopy(EXAMPLES["messages"][0]["markers"][1])
    payload.update(status=status, request_id=request_id, error=error)
    with pytest.raises(ValidationError):
        MarkerState.model_validate_json(json.dumps(payload))


def test_explicit_target_and_original_file_open_contract_remain_independent() -> None:
    payload: dict[str, object] = {
        "version": PROTOCOL_VERSION,
        "type": "command",
        "id": "request-1",
        "action": {"name": "library.import"},
    }
    with pytest.raises(ValidationError):
        parse_command(json.dumps(payload))
    payload["target"] = {**EXAMPLES["target"], "generation": -1}
    with pytest.raises(ValidationError):
        parse_command(json.dumps(payload))
    with pytest.raises(ValidationError):
        Command.model_validate_json('{"path":"example.forces","new_window":true}')
    assert OpenRequest.model_validate_json(
        '{"path":"example.forces","new_window":true}',
    ) == OpenRequest(
        path="example.forces",
        new_window=True,
    )
