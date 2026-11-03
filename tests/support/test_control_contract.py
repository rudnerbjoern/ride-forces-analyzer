"""Shared Python/TypeScript control messages and strict wire-boundary regressions."""

from copy import deepcopy
import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from ride_forces_analyzer.runtime.control_contract import (
    ActionName,
    PROTOCOL_VERSION,
    Command,
    Failure,
    MarkerState,
    parse_command,
    parse_server_message,
    Result,
    StateEvent,
)
from ride_forces_analyzer.runtime.instance import OpenRequest

FIXTURE = Path(__file__).parents[2] / "tests/fixtures/stream_deck_protocol.json"
EXAMPLES = json.loads(FIXTURE.read_text(encoding="utf-8"))


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


@pytest.mark.parametrize("version", [True, "2", 0, 1, 3])
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
        {"name": "library.open", "new_window": True},
        {"name": "library.move", "direction": 10},
        {"name": "library.move", "direction": True},
        {"name": "position.step", "steps": 2},
        {"name": "position.step", "steps": True},
        {"name": "curve.set", "curve": "combined", "enabled": "yes"},
        {"name": "marker.preview", "marker": "missing", "steps": 1},
        {"name": "marker.apply"},
        {"name": "selection.step", "boundary": "gravity", "steps": 1},
        {"name": "selection.step", "boundary": "end", "steps": True},
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
    payload["error"] = "analysis_failed" if status == "failed" else None
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
        ("preview", None, "analysis_failed"),
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
