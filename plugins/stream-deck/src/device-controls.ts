import type { ControlSettings } from "./controls.js";
import type { MarkerName, SelectionBoundary, Steps } from "./protocol.js";

/**
 *
 */
export type DialControl =
	| "combined"
	| "display"
	| "filter"
	| "library"
	| "marker"
	| "playback"
	| "position"
	| "selection"
	| "smoothing"
	| "speed"
	| "view"
	| "zoom_selection";
/**
 *
 */
export type PlusMenu = "curves" | "library" | "markers" | "playback";
/**
 *
 */
export type LibraryFilter = "park" | "status";
/**
 *
 */
export type DialSettings = {
	/**
	 *
	 */
	control?: DialControl;
	/**
	 *
	 */
	marker?: MarkerName;
	/**
	 *
	 */
	boundary?: SelectionBoundary;
	/**
	 *
	 */
	filter?: LibraryFilter;
	/**
	 *
	 */
	menu?: PlusMenu;
	/**
	 *
	 */
	column?: 0 | 1 | 2 | 3;
};
/**
 *
 */
export type InfoSettings = {
	/**
	 *
	 */
	section?: string;
	/**
	 *
	 */
	marker?: MarkerName;
	/**
	 *
	 */
	boundary?: SelectionBoundary;
};

/**
 *
 */
export type StepSize = 1 | 10 | 20;

/** Device-local step size survives menus, starts at one and never changes app state. */
export class StepMode {
	/**
	 *
	 */
	private readonly devices = new Map<string, StepSize>();
	/**
	 *
	 */
	private readonly listeners = new Set<() => void>();
	/**
	 * Read this device's current sample increment.
	 * @param device SDK device identifier whose step size is requested.
	 * @returns Selected sample count, defaulting to one for a new device.
	 */
	public samples(device: string): StepSize {
		return this.devices.get(device) ?? 1;
	}
	/**
	 * Subscribe to device-local sample-step changes.
	 * @param listener Callback invoked after a device changes its sample increment.
	 */
	public subscribe(listener: () => void): void {
		this.listeners.add(listener);
	}
	/**
	 * Cycle one device through one, ten and twenty source samples.
	 * @param device SDK device identifier whose step size should advance.
	 */
	public toggle(device: string): void {
		const current = this.samples(device);
		this.devices.set(device, current === 1 ? 10 : current === 10 ? 20 : 1);
		for (const listener of this.listeners) listener();
	}
}

/**
 * Validate profile settings before mapping a gesture to an application action.
 * @param value Untrusted dial settings supplied by the native profile.
 * @returns Validated settings, or undefined for unsupported or malformed bindings.
 */
export function dialSettings(value: DialSettings): DialSettings | undefined {
	if (
		![
			"library",
			"position",
			"view",
			"smoothing",
			"speed",
			"marker",
			"selection",
			"zoom_selection",
			"combined",
			"playback",
			"filter",
			"display",
		].includes(value.control ?? "")
	)
		return undefined;
	if (value.menu !== undefined && !["library", "playback", "curves", "markers"].includes(value.menu)) return undefined;
	if (value.column !== undefined && ![0, 1, 2, 3].includes(value.column)) return undefined;
	if (value.control === "filter" && value.filter !== "park" && value.filter !== "status") return undefined;
	if (value.control === "marker" && !["start", "gravity", "incline", "end"].includes(value.marker ?? ""))
		return undefined;
	if (value.control === "selection" && !["start", "end"].includes(value.boundary ?? "")) return undefined;
	return value;
}

/**
 * Identify controls whose unused rotation and touch gestures remain silent.
 * @param control Configured dial control, if one was selected.
 * @returns Whether the control accepts only a dial press.
 */
export function isPressOnly(control: DialControl | undefined): boolean {
	return control === "zoom_selection" || control === "combined" || control === "playback";
}

/**
 * Map one gesture to an existing key-style application operation.
 * @param settings Validated control and optional marker, boundary or filter binding.
 * @param gesture Dial input being mapped: rotation, press or touch.
 * @param direction Signed direction for this individual rotation tick.
 * @param stepSize Device-local source-sample count used for position and marker steps.
 * @returns Control binding for this gesture, or undefined when it has no action.
 */
export function dialBinding(
	settings: DialSettings,
	gesture: "press" | "rotate" | "touch",
	direction: -1 | 1,
	stepSize: StepSize,
): ControlSettings | undefined {
	const control = settings.control;
	const steps = (direction * stepSize) as Steps;
	if (isPressOnly(control)) {
		if (gesture !== "press") return undefined;
		return control === "combined"
			? { operation: "curve.set", curve: "combined" }
			: { operation: control === "playback" ? "playback.toggle" : "view.selection" };
	}
	if (control === "selection") {
		return gesture === "rotate" && settings.boundary
			? { operation: "selection.step", boundary: settings.boundary, steps }
			: undefined;
	}
	if (control === "marker") {
		const marker = settings.marker;
		if (!marker) return undefined;
		return gesture === "rotate"
			? { operation: "marker.preview", marker, steps }
			: { operation: gesture === "press" ? "marker.apply" : "marker.discard", marker };
	}
	if (gesture === "touch") return undefined;
	if (gesture === "press") {
		switch (control) {
			case "library":
				return { operation: "library.open.same" };
			case "position":
				return { operation: "playback.toggle" };
			case "view":
				return { operation: "view.reset" };
			case "smoothing":
				return { operation: "smoothing.reset" };
			case "speed":
				return { operation: "playback.speed.reset" };
			default:
				return undefined;
		}
	}
	switch (control) {
		case "library":
			return { operation: "library.move", direction };
		case "position":
			return { operation: "position.step", steps };
		case "view":
			return { operation: "view.zoom", direction };
		case "smoothing":
			return { operation: "smoothing.step", direction };
		case "speed":
			return { operation: "playback.speed.step", direction };
		default:
			return undefined;
	}
}
