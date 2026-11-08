import type { Action, CurveName, Direction, MarkerName, SelectionBoundary, StateEvent, Steps } from "./protocol.js";

/**
 *
 */
type ControlOperation = Exclude<Action["name"], "library.filter.set">;

/**
 *
 */
export type ControlSettings = {
	/**
	 *
	 */
	operation?: ControlOperation;
	/**
	 *
	 */
	direction?: Direction;
	/**
	 *
	 */
	steps?: Steps;
	/**
	 *
	 */
	curve?: CurveName;
	/**
	 *
	 */
	marker?: MarkerName;
	/**
	 *
	 */
	boundary?: SelectionBoundary;
};

export const CONTROL_LABELS: Readonly<Record<ControlOperation, string>> = {
	"library.open.new": "Library: open selection in new window",
	"library.filter.reset": "Library: reset filters",
	"library.move": "Library: select entry",
	"library.open.same": "Library: open selection",
	"library.import": "Library: import…",
	"playback.toggle": "Play / Pause",
	"playback.speed.step": "Playback speed",
	"playback.speed.reset": "Reset playback speed",
	"selection.step": "Selection: adjust boundary",
	"position.step": "Step position",
	"view.zoom": "Zoom",
	"view.reset": "Reset view",
	"view.selection": "Zoom to selection",
	"smoothing.step": "Smoothing",
	"smoothing.reset": "Reset smoothing",
	"curve.set": "Curve / calibrated mode",
	"marker.preview": "Marker: preview",
	"marker.apply": "Marker: apply",
	"marker.discard": "Marker: discard",
};

/**
 * Validate persisted key settings before selecting an application action.
 * @param value Untrusted settings read from the native action configuration.
 * @returns Normalized control settings, or undefined when settings are invalid.
 */
export function controlSettings(value: Record<string, unknown>): ControlSettings | undefined {
	const operation = value.operation ?? "playback.toggle";
	if (typeof operation !== "string" || !Object.hasOwn(CONTROL_LABELS, operation)) return undefined;
	const direction = value.direction ?? 1;
	const steps = value.steps ?? 1;
	const curve = value.curve ?? "first";
	const marker = value.marker ?? "start";
	const boundary = value.boundary ?? "start";
	if (
		(direction !== -1 && direction !== 1) ||
		(steps !== -20 && steps !== -10 && steps !== -1 && steps !== 1 && steps !== 10 && steps !== 20) ||
		(curve !== "first" && curve !== "second" && curve !== "third" && curve !== "combined" && curve !== "calibrated") ||
		(boundary !== "start" && boundary !== "end") ||
		(marker !== "start" && marker !== "gravity" && marker !== "incline" && marker !== "end")
	)
		return undefined;
	return { operation: operation as ControlOperation, direction, steps, curve, marker, boundary };
}

/**
 * Build commands from confirmed values and current action availability.
 * @param settings Validated key binding identifying the desired operation.
 * @param state Latest confirmed application snapshot, if connected.
 * @returns Available typed command, or undefined when the operation cannot run.
 */
export function requestedAction(settings: ControlSettings, state: StateEvent | undefined): Action | undefined {
	const name = settings.operation ?? "playback.toggle";
	if (!state?.target || !state.availability.available || !state.controls[name]?.available) return undefined;
	switch (name) {
		case "library.move":
			return { name, direction: settings.direction ?? 1 };
		case "position.step":
			return { name, steps: settings.steps ?? 1 };
		case "selection.step":
			return state.selection ? { name, boundary: settings.boundary ?? "start", steps: settings.steps ?? 1 } : undefined;
		case "playback.speed.step":
		case "smoothing.step":
		case "view.zoom":
			return { name, direction: settings.direction ?? 1 };
		case "curve.set": {
			const curve = state.curves.find((value) => value.curve === (settings.curve ?? "first"));
			return curve?.availability.available ? { name, curve: curve.curve, enabled: !curve.active } : undefined;
		}
		case "marker.preview":
		case "marker.apply":
		case "marker.discard": {
			const marker = state.markers.find((value) => value.marker === (settings.marker ?? "start"));
			const choice = name === "marker.preview" ? "preview" : name === "marker.apply" ? "apply" : "discard";
			if (!marker?.availability[choice].available) return undefined;
			return name === "marker.preview"
				? { name, marker: marker.marker, steps: settings.steps ?? 1 }
				: { name, marker: marker.marker };
		}
		default:
			return { name };
	}
}
