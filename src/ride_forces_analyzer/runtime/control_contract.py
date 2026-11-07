"""Versioned Stream Deck wire models, independent of Qt and application actions.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

PROTOCOL_VERSION = 3
Version = Annotated[int, Field(ge=PROTOCOL_VERSION, le=PROTOCOL_VERSION)]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
SampleIndex = Annotated[int, Field(ge=0)]
Direction = Literal[-1, 1]
Steps = Literal[-20, -10, -1, 1, 10, 20]
SelectionBoundary = Literal["start", "end"]
MarkerName = Literal["start", "gravity", "incline", "end"]
CurveName = Literal["first", "second", "third", "combined", "calibrated"]
UnavailableReason = Literal[
    "no_active_window",
    "background",
    "input_focus",
    "dialog_open",
    "no_recording",
    "no_selection",
    "empty_library",
    "unsupported",
    "busy",
    "no_preview",
    "invalid_marker",
]
ErrorCode = Literal[
    "invalid_command",
    "unsupported_protocol",
    "stale_target",
    "unavailable",
    "analysis_failed",
]


class WireModel(BaseModel, frozen=True, strict=True, extra="forbid", allow_inf_nan=False):
    """Reject coercion, unknown fields and non-finite numbers at the wire boundary."""

    @field_validator("direction", "steps", "speed", mode="before", check_fields=False)
    @classmethod
    def _numeric_literal(cls, value: object) -> object:
        """Keep JSON booleans distinct from numeric literal choices."""
        if isinstance(value, bool):
            raise ValueError("Expected a numeric choice, not a boolean")
        return value

    @field_validator("available", mode="before", check_fields=False)
    @classmethod
    def _availability_flag(cls, value: object) -> object:
        """Require actual JSON booleans for availability discriminators."""
        if not isinstance(value, bool):
            raise ValueError("Availability must be a boolean")
        return value


class Target(WireModel, frozen=True):
    """Identify one Explorer context without relying on focus at execution time.

    Attributes:
        window_id: Opaque process-local Explorer identifier.
        recording_id: Loaded source identity, or None without a recording.
        generation: Context generation, changed on target/recording replacement.
    """

    window_id: Identifier
    recording_id: Identifier | None
    generation: Annotated[int, Field(ge=0)]


class SimpleAction(WireModel, frozen=True):
    """Request an action without arguments.

    Attributes:
        name: Existing action to invoke in the addressed Explorer.
    """

    name: Literal[
        "library.open",
        "library.open_new_window",
        "library.import",
        "library.reset_filters",
        "playback.toggle",
        "playback.speed.reset",
        "view.reset",
        "view.selection",
        "smoothing.reset",
    ]


class LibraryMove(WireModel, frozen=True):
    """Move one visible Library entry with cyclic boundaries.

    Attributes:
        name: Library navigation discriminator.
        direction: Previous (-1) or next (1), without acceleration.
    """

    name: Literal["library.move"]
    direction: Direction


class PositionStep(WireModel, frozen=True):
    """Adjust playback position using the agreed fine/coarse sample steps.

    Attributes:
        name: Position navigation discriminator.
        steps: Signed source-sample count, clamped by the application.
    """

    name: Literal["position.step"]
    steps: Steps


class SelectionStep(WireModel, frozen=True):
    """Adjust one inclusive export-selection boundary independently of ride markers.

    Attributes:
        name: Selection-boundary adjustment discriminator.
        boundary: Start or end of the current selection.
        steps: Signed source-sample count; existing selection controls clamp it.
    """

    name: Literal["selection.step"]
    boundary: SelectionBoundary
    steps: Steps


class SettingStep(WireModel, frozen=True):
    """Move to an adjacent existing setting or zoom level.

    Attributes:
        name: Setting discriminator.
        direction: Previous/decrease (-1) or next/increase (1).
    """

    name: Literal["playback.speed.step", "smoothing.step", "view.zoom"]
    direction: Direction


class CurveSet(WireModel, frozen=True):
    """Set visibility or calibrated mode from confirmed application state.

    Attributes:
        name: Curve-setting discriminator.
        curve: Stable control slot; axis labels come from state.
        enabled: Requested value, subject to application availability.
    """

    name: Literal["curve.set"]
    curve: CurveName
    enabled: bool


class MarkerPreview(WireModel, frozen=True):
    """Adjust one marker preview without applying or persisting it.

    Attributes:
        name: Preview discriminator.
        marker: Marker in Start/Gravity/Incline/End order.
        steps: Signed source-sample count, clamped to valid marker bounds.
    """

    name: Literal["marker.preview"]
    marker: MarkerName
    steps: Steps


class MarkerDecision(WireModel, frozen=True):
    """Apply or discard only the addressed marker preview.

    Attributes:
        name: Preview confirmation or discard discriminator.
        marker: Marker whose preview is affected.
    """

    name: Literal["marker.apply", "marker.discard"]
    marker: MarkerName


Action = Annotated[
    SimpleAction
    | LibraryMove
    | PositionStep
    | SelectionStep
    | SettingStep
    | CurveSet
    | MarkerPreview
    | MarkerDecision,
    Field(discriminator="name"),
]
ActionName = Literal[
    "library.open",
    "library.open_new_window",
    "library.import",
    "library.reset_filters",
    "library.move",
    "playback.toggle",
    "playback.speed.reset",
    "playback.speed.step",
    "position.step",
    "selection.step",
    "view.reset",
    "view.selection",
    "view.zoom",
    "smoothing.reset",
    "smoothing.step",
    "curve.set",
    "marker.preview",
    "marker.apply",
    "marker.discard",
]


class Command(WireModel, frozen=True):
    """Carry one request correlated with its response and explicit target.

    Attributes:
        version: Exact application protocol version, separate from transport auth.
        type: Command envelope discriminator.
        id: Unique request ID within the authenticated connection.
        target: Context copied from the latest state; never implicitly redirected.
        action: Typed action and its arguments.
    """

    version: Version
    type: Literal["command"]
    id: Identifier
    target: Target
    action: Action


class Available(WireModel, frozen=True):
    """Describe an enabled application control.

    Attributes:
        available: True when the application permits execution.
    """

    available: Literal[True]


class Unavailable(WireModel, frozen=True):
    """Explain why an application control cannot execute.

    Attributes:
        available: False when execution is blocked.
        reason: Stable machine-readable cause for device feedback.
    """

    available: Literal[False]
    reason: UnavailableReason


Availability = Available | Unavailable


class Position(WireModel, frozen=True):
    """Provide an existing application value and its formatted display label.

    Attributes:
        sample: Zero-based source-sample index.
        time_seconds: Source time in seconds, without a guessed sampling rate.
        label: Application-formatted replay time, including preview-relative labels.
    """

    sample: SampleIndex
    time_seconds: float
    label: str


class LibraryEntry(WireModel, frozen=True):
    """Describe the selected visible Library entry without exporting the full list.

    Attributes:
        id: Archived recording identity.
        title: Displayed entry title.
        index: Zero-based position in the current visible ordering.
    """

    id: Identifier
    title: str
    index: SampleIndex


class LibraryState(WireModel, frozen=True):
    """Expose current filtered Library navigation values.

    Attributes:
        count: Number of entries in the visible sorted/filtered list.
        selected: Current selection, or None without a selection.
    """

    count: Annotated[int, Field(ge=0)]
    selected: LibraryEntry | None


class PlaybackState(WireModel, frozen=True):
    """Expose confirmed playback state and available position bounds.

    Attributes:
        playing: Actual playback activity.
        speed: Existing supported playback multiplier.
        position: Current source position and displayed replay label.
        last_sample: Last valid source index, or None without a recording.
    """

    playing: bool
    speed: float
    position: Position | None
    last_sample: SampleIndex | None

    @field_validator("speed")
    @classmethod
    def _supported_speed(cls, value: float) -> float:
        """Accept only the application's existing playback multipliers."""
        if value not in {0.5, 1.0, 2.0}:
            raise ValueError("Unsupported playback speed")
        return value


class SelectionState(WireModel, frozen=True):
    """Expose the confirmed inclusive selection without changing recording markers.

    Attributes:
        start: First selected source sample and its displayed time.
        end: Last selected source sample and its displayed time.
    """

    start: Position
    end: Position

    @model_validator(mode="after")
    def ordered(self) -> Self:
        """Reject selection feedback whose start follows its end.

        Returns:
            The validated selection.

        Raises:
            ValueError: The inclusive bounds are reversed.
        """
        if self.start.sample > self.end.sample:
            raise ValueError("Selection start must not exceed its end")
        return self


class ViewState(WireModel, frozen=True):
    """Expose chart interval and existing smoothing values.

    Attributes:
        start_seconds: Visible source-time start, or None without a chart.
        end_seconds: Visible source-time end, or None without a chart.
        smoothing_window: Actual odd sample-window size, or None without data.
    """

    start_seconds: float | None
    end_seconds: float | None
    smoothing_window: Annotated[int, Field(ge=1)] | None

    @field_validator("smoothing_window")
    @classmethod
    def _odd_window(cls, value: int | None) -> int | None:
        """Reject even windows while retaining the application's odd sample sizes."""
        if value is not None and value % 2 == 0:
            raise ValueError("Smoothing window must be odd")
        return value


class CurveState(WireModel, frozen=True):
    """Expose a curve/mode control independently of its availability.

    Attributes:
        curve: Stable control slot, including Combined and calibrated mode.
        label: Actual directional or raw-axis label from the application.
        active: Confirmed effective visibility or mode.
        availability: Whether the user may change this control.
    """

    curve: CurveName
    label: str
    active: bool
    availability: Availability


class MarkerState(WireModel, frozen=True):
    """Distinguish preview, pending analysis and adopted marker values.

    Attributes:
        marker: Marker identity.
        applied: Last successfully adopted position, or None when unset.
        preview: Unconfirmed position, or None without a preview.
        status: Applied, preview, pending or failed application state.
        request_id: Pending/completed apply request, or None without one.
        error: Application failure code, or None without a failure.
        availability: Per-marker command availability.
    """

    marker: MarkerName
    applied: Position | None
    preview: Position | None
    status: Literal["applied", "preview", "pending", "failed"]
    request_id: Identifier | None
    error: ErrorCode | None
    availability: dict[Literal["preview", "apply", "discard"], Availability]

    @model_validator(mode="after")
    def _consistent_status(self) -> Self:
        """Keep confirmed, proposed and failed values distinct on the wire."""
        if (self.status == "applied") != (self.preview is None):
            raise ValueError("Only applied marker status has no preview")
        if self.status in {"pending", "failed"} and self.request_id is None:
            raise ValueError("Pending or failed application requires its request ID")
        if self.status == "failed":
            if self.error != "analysis_failed":
                raise ValueError("Failed marker application requires analysis_failed")
        elif self.error is not None:
            raise ValueError("Only failed marker status carries an error")
        return self


class StateEvent(WireModel, frozen=True):
    """Publish a full confirmed snapshot after auth and subsequent state changes.

    Attributes:
        version: Exact application protocol version.
        type: State envelope discriminator.
        session_id: Opaque server-session identity, never an authentication token.
        sequence: Monotonic snapshot number within this server session.
        target: Active Explorer context, or None without one.
        availability: Global foreground/editing/modal availability.
        controls: Supported actions and their current availability.
        library: Visible Library selection feedback, or None without a target.
        playback: Actual playback feedback, or None without a recording.
        view: Chart/smoothing feedback, or None without a recording.
        selection: Inclusive selection feedback, or None without a recording.
        curves: Curve/mode controls; empty without a recording.
        markers: Marker states; empty without a recording.
    """

    version: Version
    type: Literal["state"]
    session_id: Identifier
    sequence: Annotated[int, Field(ge=0)]
    target: Target | None
    availability: Availability
    controls: dict[ActionName, Availability]
    library: LibraryState | None
    playback: PlaybackState | None
    view: ViewState | None
    selection: SelectionState | None
    curves: tuple[CurveState, ...]
    markers: tuple[MarkerState, ...]


class Result(WireModel, frozen=True):
    """Acknowledge completion or accepted asynchronous application.

    Attributes:
        version: Exact application protocol version.
        type: Response envelope discriminator.
        id: Original request ID.
        target: Original addressed context, even if focus has since changed.
        status: Done, or pending until a final response and state confirm adoption.
    """

    version: Version
    type: Literal["response"]
    id: Identifier
    target: Target
    status: Literal["ok", "pending"]


class Failure(WireModel, frozen=True):
    """Reject a request or report unsuccessful asynchronous application.

    Attributes:
        version: Server-supported application protocol version.
        type: Response envelope discriminator.
        id: Request ID, or None when no valid ID could be recovered.
        target: Addressed context, or None for malformed requests.
        status: Error discriminator; no successful adoption is implied.
        code: Stable rejection/application failure code.
        reason: Availability cause for unavailable errors, otherwise None.
    """

    version: Version
    type: Literal["response"]
    id: Identifier | None
    target: Target | None
    status: Literal["error"]
    code: ErrorCode
    reason: UnavailableReason | None


ServerMessage = StateEvent | Result | Failure
_SERVER_MESSAGE = TypeAdapter(ServerMessage)


def parse_command(payload: str) -> Command:
    """Validate an application command without executing it.

    Args:
        payload: One authenticated WebSocket text frame.

    Returns:
        A strict, immutable command envelope.

    Raises:
        pydantic.ValidationError: If the version, shape or arguments are invalid.
    """
    return Command.model_validate_json(payload)


def parse_server_message(payload: str) -> ServerMessage:
    """Validate one response or complete state snapshot.

    Args:
        payload: Application-owned server text, excluding transport ready frames.

    Returns:
        The matching state, successful response or failure model.

    Raises:
        pydantic.ValidationError: If the version, shape or values are invalid.
    """
    return _SERVER_MESSAGE.validate_json(payload)
