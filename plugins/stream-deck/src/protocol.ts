/** Application protocol; independent of the transport authentication version. */
export const PROTOCOL_VERSION = 3;

/**
 *
 */
export type Direction = -1 | 1;
/**
 *
 */
export type Steps = -1 | -10 | -20 | 1 | 10 | 20;
/**
 *
 */
export type SelectionBoundary = "end" | "start";
/**
 *
 */
export type MarkerName = "end" | "gravity" | "incline" | "start";
/** First/second/third follow the current chart axes; labels come from state. */
export type CurveName = "calibrated" | "combined" | "first" | "second" | "third";
/**
 *
 */
export type UnavailableReason =
	| "application.background"
	| "application.busy"
	| "dialog.open"
	| "input.focused"
	| "library.empty"
	| "marker.invalid"
	| "operation.unsupported"
	| "preview.missing"
	| "recording.missing"
	| "selection.missing"
	| "window.active.missing";
/**
 *
 */
export type ErrorCode =
	"analysis.failed" | "command.invalid" | "command.unavailable" | "protocol.unsupported" | "target.stale";
/** Connection state is local; no disconnected event can arrive over a closed socket. */
export type ConnectionState = "connected" | "connecting" | "disconnected" | "incompatible";
/**
 *
 */
export type Availability =
	| {
			/** Whether this action is currently admitted. */
			readonly available: false;

			/** Confirmed reason preventing the action. */
			readonly reason: UnavailableReason;
	  }
	| {
			/** Whether this action is currently admitted. */
			readonly available: true;
	  };

export interface Target {
	/**
	 *
	 */
	readonly window_id: string;
	/**
	 *
	 */
	readonly recording_id: string | null;
	/**
	 *
	 */
	readonly generation: number;
}

/**
 *
 */
export type Action =
	| {
			/** Application operation selected by this command. */
			readonly name:
				| "library.filter.reset"
				| "library.import"
				| "library.open.new"
				| "library.open.same"
				| "playback.speed.reset"
				| "playback.toggle"
				| "smoothing.reset"
				| "view.reset"
				| "view.selection";
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "curve.set";

			/** Curve or data-mode toggle to change. */
			readonly curve: CurveName;

			/** Requested toggle value, derived from confirmed state. */
			readonly enabled: boolean;
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "library.filter.set";

			/** Library filter whose value should change. */
			readonly filter: "park" | "status";

			/** Exact option value; null means All and an empty park means Unknown. */
			readonly value: string | null;
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "library.move";

			/** Signed single-step direction. */
			readonly direction: Direction;
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "marker.apply" | "marker.discard";

			/** Recording marker addressed by this command. */
			readonly marker: MarkerName;
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "marker.preview";

			/** Recording marker addressed by this command. */
			readonly marker: MarkerName;

			/** Signed source-sample increment. */
			readonly steps: Steps;
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "playback.speed.step" | "smoothing.step" | "view.zoom";

			/** Signed single-step direction. */
			readonly direction: Direction;
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "position.step";

			/** Signed source-sample increment. */
			readonly steps: Steps;
	  }
	| {
			/** Application operation selected by this command. */
			readonly name: "selection.step";

			/** Inclusive selection endpoint to adjust. */
			readonly boundary: SelectionBoundary;

			/** Signed source-sample increment. */
			readonly steps: Steps;
	  };

export interface Command {
	/**
	 *
	 */
	readonly version: typeof PROTOCOL_VERSION;
	/**
	 *
	 */
	readonly type: "command";
	/**
	 *
	 */
	readonly id: string;
	/**
	 *
	 */
	readonly target: Target;
	/**
	 *
	 */
	readonly action: Action;
}

export interface Position {
	/**
	 *
	 */
	readonly sample: number;
	/**
	 *
	 */
	readonly time_seconds: number;
	/**
	 *
	 */
	readonly label: string;
}

export interface LibraryFilterOption {
	/** Verbatim user text is not an opaque identifier; null means All, empty park means Unknown. */
	readonly value: string | null;
	/**
	 *
	 */
	readonly label: string;
}

export interface LibraryFilterState {
	/**
	 *
	 */
	readonly value: string | null;
	/**
	 *
	 */
	readonly options: readonly LibraryFilterOption[];
}

export interface LibraryState {
	/**
	 *
	 */
	readonly count: number;
	/**
	 *
	 */
	readonly selected: {
		/**
		 *
		 */
		readonly id: string;
		/**
		 *
		 */
		readonly title: string;
		/**
		 *
		 */
		readonly index: number;
	} | null;
	/**
	 *
	 */
	readonly park_filter: LibraryFilterState;
	/**
	 *
	 */
	readonly status_filter: LibraryFilterState;
}

export interface PlaybackState {
	/**
	 *
	 */
	readonly playing: boolean;
	/**
	 *
	 */
	readonly speed: 0.5 | 1 | 2;
	/**
	 *
	 */
	readonly position: Position | null;
	/**
	 *
	 */
	readonly last_sample: number | null;
}

export interface SelectionState {
	/**
	 *
	 */
	readonly start: Position;
	/**
	 *
	 */
	readonly end: Position;
}

export interface ViewState {
	/**
	 *
	 */
	readonly start_seconds: number | null;
	/**
	 *
	 */
	readonly end_seconds: number | null;
	/**
	 *
	 */
	readonly smoothing_window: number | null;
}

export interface CurveState {
	/**
	 *
	 */
	readonly curve: CurveName;
	/**
	 *
	 */
	readonly label: string;
	/**
	 *
	 */
	readonly active: boolean;
	/**
	 *
	 */
	readonly availability: Availability;
}

interface MarkerValues {
	/**
	 *
	 */
	readonly marker: MarkerName;
	/**
	 *
	 */
	readonly applied: Position | null;
	/**
	 *
	 */
	readonly availability: Readonly<Record<"apply" | "discard" | "preview", Availability>>;
}

/**
 *
 */
export type MarkerState = MarkerValues &
	(
		| {
				/** Confirmed marker preview or adoption phase. */
				readonly status: "applied";

				/** Proposed marker position, independent of the adopted position. */
				readonly preview: null;

				/** Apply-request identity, or null when no request is associated. */
				readonly request_id: string | null;

				/** Analysis failure code, or null when no failure is retained. */
				readonly error: null;
		  }
		| {
				/** Confirmed marker preview or adoption phase. */
				readonly status: "failed";

				/** Proposed marker position, independent of the adopted position. */
				readonly preview: Position;

				/** Apply-request identity, or null when no request is associated. */
				readonly request_id: string;

				/** Analysis failure code, or null when no failure is retained. */
				readonly error: "analysis.failed";
		  }
		| {
				/** Confirmed marker preview or adoption phase. */
				readonly status: "pending";

				/** Proposed marker position, independent of the adopted position. */
				readonly preview: Position;

				/** Apply-request identity, or null when no request is associated. */
				readonly request_id: string;

				/** Analysis failure code, or null when no failure is retained. */
				readonly error: null;
		  }
		| {
				/** Confirmed marker preview or adoption phase. */
				readonly status: "preview";

				/** Proposed marker position, independent of the adopted position. */
				readonly preview: Position;

				/** Apply-request identity, or null when no request is associated. */
				readonly request_id: string | null;

				/** Analysis failure code, or null when no failure is retained. */
				readonly error: null;
		  }
	);

export interface StateEvent {
	/**
	 *
	 */
	readonly version: typeof PROTOCOL_VERSION;
	/**
	 *
	 */
	readonly type: "state";
	/**
	 *
	 */
	readonly session_id: string;
	/**
	 *
	 */
	readonly sequence: number;
	/**
	 *
	 */
	readonly target: Target | null;
	/**
	 *
	 */
	readonly availability: Availability;
	/** Missing controls are unsupported and must be disabled. */
	readonly controls: Readonly<Partial<Record<Action["name"], Availability>>>;
	/**
	 *
	 */
	readonly library: LibraryState | null;
	/**
	 *
	 */
	readonly playback: PlaybackState | null;
	/**
	 *
	 */
	readonly view: ViewState | null;
	/**
	 *
	 */
	readonly selection: SelectionState | null;
	/**
	 *
	 */
	readonly curves: readonly CurveState[];
	/**
	 *
	 */
	readonly markers: readonly MarkerState[];
}

/**
 *
 */
export type Response =
	| {
			/**
			 *
			 */
			readonly version: typeof PROTOCOL_VERSION;
			/**
			 *
			 */
			readonly type: "response";
			/**
			 *
			 */
			readonly id: string | null;
			/**
			 *
			 */
			readonly target: Target | null;
			/**
			 *
			 */
			readonly status: "error";
			/**
			 *
			 */
			readonly code: ErrorCode;
			/**
			 *
			 */
			readonly reason: UnavailableReason | null;
	  }
	| {
			/**
			 *
			 */
			readonly version: typeof PROTOCOL_VERSION;
			/**
			 *
			 */
			readonly type: "response";
			/**
			 *
			 */
			readonly id: string;
			/**
			 *
			 */
			readonly target: Target;
			/**
			 *
			 */
			readonly status: "ok" | "pending";
	  };

/**
 *
 */
export type ServerMessage = Response | StateEvent;
