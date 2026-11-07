/** Application protocol; independent of the transport authentication version. */
export const PROTOCOL_VERSION = 3;

export type Direction = -1 | 1;
export type Steps = -20 | -10 | -1 | 1 | 10 | 20;
export type SelectionBoundary = "start" | "end";
export type MarkerName = "start" | "gravity" | "incline" | "end";
/** First/second/third follow the current chart axes; labels come from state. */
export type CurveName = "first" | "second" | "third" | "combined" | "calibrated";
export type UnavailableReason = "no_active_window" | "background" | "input_focus"
    | "dialog_open" | "no_recording" | "no_selection" | "empty_library"
    | "unsupported" | "busy" | "no_preview" | "invalid_marker";
export type ErrorCode = "invalid_command" | "unsupported_protocol" | "stale_target"
    | "unavailable" | "analysis_failed";
/** Connection state is local; no disconnected event can arrive over a closed socket. */
export type ConnectionState = "disconnected" | "connecting" | "connected" | "incompatible";
export type Availability = { readonly available: true }
    | { readonly available: false; readonly reason: UnavailableReason };

export interface Target {
    readonly window_id: string;
    readonly recording_id: string | null;
    readonly generation: number;
}

export type Action =
    | { readonly name: "library.open" | "library.open_new_window" | "library.import" | "library.reset_filters" | "playback.toggle"
        | "playback.speed.reset" | "view.reset" | "view.selection" | "smoothing.reset" }
    | { readonly name: "library.move"; readonly direction: Direction }
    | { readonly name: "position.step"; readonly steps: Steps }
    | { readonly name: "selection.step"; readonly boundary: SelectionBoundary; readonly steps: Steps }
    | { readonly name: "playback.speed.step" | "smoothing.step" | "view.zoom";
        readonly direction: Direction }
    | { readonly name: "curve.set"; readonly curve: CurveName; readonly enabled: boolean }
    | { readonly name: "marker.preview"; readonly marker: MarkerName; readonly steps: Steps }
    | { readonly name: "marker.apply" | "marker.discard"; readonly marker: MarkerName };

export interface Command {
    readonly version: typeof PROTOCOL_VERSION;
    readonly type: "command";
    readonly id: string;
    readonly target: Target;
    readonly action: Action;
}

export interface Position {
    readonly sample: number;
    readonly time_seconds: number;
    readonly label: string;
}

export interface LibraryState {
    readonly count: number;
    readonly selected: { readonly id: string; readonly title: string; readonly index: number } | null;
}

export interface PlaybackState {
    readonly playing: boolean;
    readonly speed: 0.5 | 1 | 2;
    readonly position: Position | null;
    readonly last_sample: number | null;
}

export interface SelectionState {
    readonly start: Position;
    readonly end: Position;
}

export interface ViewState {
    readonly start_seconds: number | null;
    readonly end_seconds: number | null;
    readonly smoothing_window: number | null;
}

export interface CurveState {
    readonly curve: CurveName;
    readonly label: string;
    readonly active: boolean;
    readonly availability: Availability;
}

interface MarkerValues {
    readonly marker: MarkerName;
    readonly applied: Position | null;
    readonly availability: Readonly<Record<"preview" | "apply" | "discard", Availability>>;
}

export type MarkerState = MarkerValues & (
    | { readonly status: "applied"; readonly preview: null;
        readonly request_id: string | null; readonly error: null }
    | { readonly status: "preview"; readonly preview: Position;
        readonly request_id: string | null; readonly error: null }
    | { readonly status: "pending"; readonly preview: Position;
        readonly request_id: string; readonly error: null }
    | { readonly status: "failed"; readonly preview: Position;
        readonly request_id: string; readonly error: "analysis_failed" }
);

export interface StateEvent {
    readonly version: typeof PROTOCOL_VERSION;
    readonly type: "state";
    readonly session_id: string;
    readonly sequence: number;
    readonly target: Target | null;
    readonly availability: Availability;
    /** Missing controls are unsupported and must be disabled. */
    readonly controls: Readonly<Partial<Record<Action["name"], Availability>>>;
    readonly library: LibraryState | null;
    readonly playback: PlaybackState | null;
    readonly view: ViewState | null;
    readonly selection: SelectionState | null;
    readonly curves: readonly CurveState[];
    readonly markers: readonly MarkerState[];
}

export type Response = {
    readonly version: typeof PROTOCOL_VERSION;
    readonly type: "response";
    readonly id: string;
    readonly target: Target;
    readonly status: "ok" | "pending";
} | {
    readonly version: typeof PROTOCOL_VERSION;
    readonly type: "response";
    readonly id: string | null;
    readonly target: Target | null;
    readonly status: "error";
    readonly code: ErrorCode;
    readonly reason: UnavailableReason | null;
};

export type ServerMessage = StateEvent | Response;
