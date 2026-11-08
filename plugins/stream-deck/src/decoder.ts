import { PROTOCOL_VERSION } from "./protocol.js";
import type { ServerMessage } from "./protocol.js";

const actions = new Set([
	"library.open.same",
	"library.open.new",
	"library.import",
	"library.filter.reset",
	"library.move",
	"library.filter.set",
	"playback.toggle",
	"playback.speed.reset",
	"playback.speed.step",
	"position.step",
	"view.reset",
	"view.selection",
	"view.zoom",
	"smoothing.reset",
	"smoothing.step",
	"selection.step",
	"curve.set",
	"marker.preview",
	"marker.apply",
	"marker.discard",
]);
const reasons = new Set([
	"window.active.missing",
	"application.background",
	"input.focused",
	"dialog.open",
	"recording.missing",
	"selection.missing",
	"library.empty",
	"operation.unsupported",
	"application.busy",
	"preview.missing",
	"marker.invalid",
]);
const errors = new Set([
	"command.invalid",
	"protocol.unsupported",
	"target.stale",
	"command.unavailable",
	"analysis.failed",
]);
const markers = new Set(["start", "gravity", "incline", "end"]);
const curves = new Set(["first", "second", "third", "combined", "calibrated"]);

/**
 * Check for a non-null, non-array object.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is a non-null object that is not an array.
 */
function record(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
/**
 * Check a record's property count and required field names.
 * @param value Untrusted decoded value to validate.
 * @param keys Exact set of required record property names.
 * @returns Whether the property count matches and every required field exists.
 */
function fields(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
	return record(value) && Object.keys(value).length === keys.length && keys.every((key) => key in value);
}
/**
 * Admit only strings contained in an allowed-value set.
 * @param value Untrusted decoded value to validate.
 * @param choices Allowed string values for this protocol field.
 * @returns Whether the value is one of the allowed strings.
 */
function member(value: unknown, choices: Set<string>): value is string {
	return typeof value === "string" && choices.has(value);
}
/**
 * Validate a nonempty opaque identifier within the protocol length bound.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is an admissible identifier.
 */
function id(value: unknown): value is string {
	return typeof value === "string" && value.length > 0 && value.length <= 128;
}
/**
 * Validate a nonnegative safe integer.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is a safe integer at or above zero.
 */
function integer(value: unknown): value is number {
	return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
/**
 * Reject non-numeric and non-finite wire values.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is a finite number.
 */
function finite(value: unknown): value is number {
	return typeof value === "number" && Number.isFinite(value);
}
/**
 * Validate the complete window, recording and generation identity.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value satisfies the target contract.
 */
function target(value: unknown): boolean {
	return (
		fields(value, ["window_id", "recording_id", "generation"]) &&
		id(value.window_id) &&
		(value.recording_id === null || id(value.recording_id)) &&
		integer(value.generation)
	);
}
/**
 * Validate available state or a recognized unavailability reason.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value satisfies the availability contract.
 */
function availability(value: unknown): boolean {
	return (
		(fields(value, ["available"]) && value.available === true) ||
		(fields(value, ["available", "reason"]) && value.available === false && member(value.reason, reasons))
	);
}
/**
 * Validate an optional sample index, time and display label.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is null or a complete valid position.
 */
function position(value: unknown): boolean {
	return (
		value === null ||
		(fields(value, ["sample", "time_seconds", "label"]) &&
			integer(value.sample) &&
			finite(value.time_seconds) &&
			typeof value.label === "string")
	);
}
/**
 * Validate ordered filter choices and an admissible confirmed value.
 * @param value Untrusted decoded value to validate.
 * @returns Whether choices are unique and the current value is admissible.
 */
function libraryFilter(value: unknown): boolean {
	if (
		!fields(value, ["value", "options"]) ||
		!(value.value === null || typeof value.value === "string") ||
		!Array.isArray(value.options)
	)
		return false;
	const choices = new Set<unknown>();
	for (const option of value.options) {
		if (
			!fields(option, ["value", "label"]) ||
			!(option.value === null || typeof option.value === "string") ||
			typeof option.label !== "string" ||
			choices.has(option.value)
		)
			return false;
		choices.add(option.value);
	}
	return choices.has(value.value) || (choices.size === 0 && value.value === null);
}
/**
 * Validate optional Library selection, counts and filter snapshots.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is null or a complete Library snapshot.
 */
function library(value: unknown): boolean {
	return (
		value === null ||
		(fields(value, ["count", "selected", "park_filter", "status_filter"]) &&
			integer(value.count) &&
			libraryFilter(value.park_filter) &&
			libraryFilter(value.status_filter) &&
			(value.selected === null ||
				(fields(value.selected, ["id", "title", "index"]) &&
					id(value.selected.id) &&
					typeof value.selected.title === "string" &&
					integer(value.selected.index))))
	);
}
/**
 * Validate optional playback state, supported speed and positions.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value satisfies the playback snapshot contract.
 */
function playback(value: unknown): boolean {
	return (
		value === null ||
		(fields(value, ["playing", "speed", "position", "last_sample"]) &&
			typeof value.playing === "boolean" &&
			[0.5, 1, 2].some((speed) => speed === value.speed) &&
			position(value.position) &&
			(value.last_sample === null || integer(value.last_sample)))
	);
}
/**
 * Validate optional inclusive selection positions in ascending order.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is null or a valid ordered selection.
 */
function selection(value: unknown): boolean {
	if (value === null) return true;
	if (!fields(value, ["start", "end"]) || !record(value.start) || !record(value.end)) return false;
	return (
		position(value.start) &&
		position(value.end) &&
		typeof value.start.sample === "number" &&
		typeof value.end.sample === "number" &&
		value.start.sample <= value.end.sample
	);
}
/**
 * Validate optional viewport bounds and an odd smoothing window.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value satisfies the view snapshot contract.
 */
function view(value: unknown): boolean {
	return (
		value === null ||
		(fields(value, ["start_seconds", "end_seconds", "smoothing_window"]) &&
			(value.start_seconds === null || finite(value.start_seconds)) &&
			(value.end_seconds === null || finite(value.end_seconds)) &&
			(value.smoothing_window === null || (integer(value.smoothing_window) && value.smoothing_window % 2 === 1)))
	);
}
/**
 * Validate a named curve's label, toggle state and availability.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is a complete valid curve snapshot.
 */
function curve(value: unknown): boolean {
	return (
		fields(value, ["curve", "label", "active", "availability"]) &&
		member(value.curve, curves) &&
		typeof value.label === "string" &&
		typeof value.active === "boolean" &&
		availability(value.availability)
	);
}
/**
 * Validate marker positions and consistent preview/adoption status.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value satisfies the marker state and availability contract.
 */
function marker(value: unknown): boolean {
	if (
		!fields(value, ["marker", "applied", "preview", "status", "request_id", "error", "availability"]) ||
		!member(value.marker, markers) ||
		!position(value.applied) ||
		!position(value.preview) ||
		!(value.request_id === null || id(value.request_id)) ||
		!fields(value.availability, ["preview", "apply", "discard"]) ||
		!Object.values(value.availability).every(availability)
	)
		return false;
	switch (value.status) {
		case "applied":
			return value.preview === null && value.error === null;
		case "preview":
			return value.preview !== null && value.error === null;
		case "pending":
			return value.preview !== null && id(value.request_id) && value.error === null;
		case "failed":
			return value.preview !== null && id(value.request_id) && value.error === "analysis.failed";
		default:
			return false;
	}
}
/**
 * Validate exact fields and supported versions for incoming server messages.
 * @param value Untrusted decoded value to validate.
 * @returns Whether the value is an admissible state or command response.
 */
function serverMessage(value: unknown): value is ServerMessage {
	if (!record(value) || value.version !== PROTOCOL_VERSION) return false;
	if (value.type === "state") {
		return (
			fields(value, [
				"version",
				"type",
				"session_id",
				"sequence",
				"target",
				"availability",
				"controls",
				"library",
				"playback",
				"view",
				"selection",
				"curves",
				"markers",
			]) &&
			id(value.session_id) &&
			integer(value.sequence) &&
			(value.target === null || target(value.target)) &&
			availability(value.availability) &&
			record(value.controls) &&
			Object.entries(value.controls).every(([name, state]) => actions.has(name) && availability(state)) &&
			library(value.library) &&
			playback(value.playback) &&
			view(value.view) &&
			selection(value.selection) &&
			Array.isArray(value.curves) &&
			value.curves.every(curve) &&
			Array.isArray(value.markers) &&
			value.markers.every(marker)
		);
	}
	if (value.type !== "response") return false;
	if (value.status === "ok" || value.status === "pending") {
		return fields(value, ["version", "type", "id", "target", "status"]) && id(value.id) && target(value.target);
	}
	return (
		fields(value, ["version", "type", "id", "target", "status", "code", "reason"]) &&
		value.status === "error" &&
		(value.id === null || id(value.id)) &&
		(value.target === null || target(value.target)) &&
		member(value.code, errors) &&
		(value.reason === null || member(value.reason, reasons))
	);
}

/**
 * Decode the bounded versioned wire contract before updating device state.
 * @param payload UTF-8 JSON server message received from Analyzer.
 * @returns Validated server message, or undefined for malformed or incompatible input.
 */
export function decodeServerMessage(payload: string): ServerMessage | undefined {
	if (Buffer.byteLength(payload, "utf8") > 64 * 1024) return undefined;
	try {
		const value: unknown = JSON.parse(payload);
		return serverMessage(value) ? value : undefined;
	} catch {
		return undefined;
	}
}
