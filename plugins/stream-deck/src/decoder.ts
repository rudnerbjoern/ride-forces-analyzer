import { PROTOCOL_VERSION } from "./protocol.js";
import type { ServerMessage } from "./protocol.js";

const actions = new Set([
    "library.open", "library.open_new_window", "library.import", "library.reset_filters", "library.move", "playback.toggle", "playback.speed.reset",
    "playback.speed.step", "position.step", "view.reset", "view.selection", "view.zoom",
    "smoothing.reset", "smoothing.step", "selection.step", "curve.set", "marker.preview", "marker.apply", "marker.discard",
]);
const reasons = new Set(["no_active_window", "background", "input_focus", "dialog_open", "no_recording",
    "no_selection", "empty_library", "unsupported", "busy", "no_preview", "invalid_marker"]);
const errors = new Set(["invalid_command", "unsupported_protocol", "stale_target", "unavailable", "analysis_failed"]);
const markers = new Set(["start", "gravity", "incline", "end"]);
const curves = new Set(["first", "second", "third", "combined", "calibrated"]);

function record(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function fields(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
    return record(value) && Object.keys(value).length === keys.length && keys.every(key => key in value);
}
function member(value: unknown, choices: Set<string>): value is string {
    return typeof value === "string" && choices.has(value);
}
function id(value: unknown): value is string {
    return typeof value === "string" && value.length > 0 && value.length <= 128;
}
function integer(value: unknown): value is number {
    return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function finite(value: unknown): value is number {
    return typeof value === "number" && Number.isFinite(value);
}
function target(value: unknown): boolean {
    return fields(value, ["window_id", "recording_id", "generation"]) && id(value.window_id)
        && (value.recording_id === null || id(value.recording_id)) && integer(value.generation);
}
function availability(value: unknown): boolean {
    return fields(value, ["available"]) && value.available === true
        || fields(value, ["available", "reason"]) && value.available === false && member(value.reason, reasons);
}
function position(value: unknown): boolean {
    return value === null || fields(value, ["sample", "time_seconds", "label"])
        && integer(value.sample) && finite(value.time_seconds) && typeof value.label === "string";
}
function library(value: unknown): boolean {
    return value === null || fields(value, ["count", "selected"]) && integer(value.count)
        && (value.selected === null || fields(value.selected, ["id", "title", "index"])
            && id(value.selected.id) && typeof value.selected.title === "string" && integer(value.selected.index));
}
function playback(value: unknown): boolean {
    return value === null || fields(value, ["playing", "speed", "position", "last_sample"])
        && typeof value.playing === "boolean" && [0.5, 1, 2].some(speed => speed === value.speed)
        && position(value.position) && (value.last_sample === null || integer(value.last_sample));
}
function selection(value: unknown): boolean {
    if (value === null) return true;
    if (!fields(value, ["start", "end"]) || !record(value.start) || !record(value.end)) return false;
    return position(value.start) && position(value.end) && typeof value.start.sample === "number"
        && typeof value.end.sample === "number" && value.start.sample <= value.end.sample;
}
function view(value: unknown): boolean {
    return value === null || fields(value, ["start_seconds", "end_seconds", "smoothing_window"])
        && (value.start_seconds === null || finite(value.start_seconds))
        && (value.end_seconds === null || finite(value.end_seconds))
        && (value.smoothing_window === null || integer(value.smoothing_window) && value.smoothing_window % 2 === 1);
}
function curve(value: unknown): boolean {
    return fields(value, ["curve", "label", "active", "availability"]) && member(value.curve, curves)
        && typeof value.label === "string" && typeof value.active === "boolean" && availability(value.availability);
}
function marker(value: unknown): boolean {
    if (!fields(value, ["marker", "applied", "preview", "status", "request_id", "error", "availability"])
        || !member(value.marker, markers) || !position(value.applied) || !position(value.preview)
        || !(value.request_id === null || id(value.request_id))
        || !fields(value.availability, ["preview", "apply", "discard"])
        || !Object.values(value.availability).every(availability)) return false;
    switch (value.status) {
        case "applied": return value.preview === null && value.error === null;
        case "preview": return value.preview !== null && value.error === null;
        case "pending": return value.preview !== null && id(value.request_id) && value.error === null;
        case "failed": return value.preview !== null && id(value.request_id) && value.error === "analysis_failed";
        default: return false;
    }
}
function serverMessage(value: unknown): value is ServerMessage {
    if (!record(value) || value.version !== PROTOCOL_VERSION) return false;
    if (value.type === "state") {
        return fields(value, ["version", "type", "session_id", "sequence", "target", "availability",
            "controls", "library", "playback", "view", "selection", "curves", "markers"])
            && id(value.session_id) && integer(value.sequence) && (value.target === null || target(value.target))
            && availability(value.availability) && record(value.controls)
            && Object.entries(value.controls).every(([name, state]) => actions.has(name) && availability(state))
            && library(value.library) && playback(value.playback) && view(value.view) && selection(value.selection)
            && Array.isArray(value.curves) && value.curves.every(curve)
            && Array.isArray(value.markers) && value.markers.every(marker);
    }
    if (value.type !== "response") return false;
    if (value.status === "ok" || value.status === "pending") {
        return fields(value, ["version", "type", "id", "target", "status"]) && id(value.id) && target(value.target);
    }
    return fields(value, ["version", "type", "id", "target", "status", "code", "reason"])
        && value.status === "error" && (value.id === null || id(value.id))
        && (value.target === null || target(value.target)) && member(value.code, errors)
        && (value.reason === null || member(value.reason, reasons));
}

/** Decode the exact v2 wire contract before any value can drive a key or command. */
export function decodeServerMessage(payload: string): ServerMessage | undefined {
    if (Buffer.byteLength(payload, "utf8") > 64 * 1024) return undefined;
    try {
        const value: unknown = JSON.parse(payload);
        return serverMessage(value) ? value : undefined;
    } catch {
        return undefined;
    }
}
