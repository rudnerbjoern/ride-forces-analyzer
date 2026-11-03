import type { ControlClient } from "./client.js";
import { dialBinding, type DialSettings, type InfoSettings } from "./device-controls.js";
import { keyFeedback, keyImage, type IconStatus } from "./feedback.js";
import type { Position } from "./protocol.js";

export type SurfaceFeedback = { icon: string; title: string; value: string; status: string; detail: string };
const label = (value: string): string => value.charAt(0).toUpperCase() + value.slice(1);
const position = (value: Position | null | undefined): string => value ? `#${value.sample} · ${value.label}` : "Unset";

/** Touch-strip feedback uses only confirmed state and clearly separates previews from applied values. */
export function dialFeedback(client: ControlClient, context: string, settings: DialSettings | undefined,
    coarse: boolean | undefined): SurfaceFeedback {
    const control = settings?.control ?? "position";
    const title = label(control === "marker" ? settings?.marker ?? "Marker" : control);
    const result: SurfaceFeedback = { icon: keyImage(control, "disconnected"), title, value: "—", status: "Offline", detail: "" };
    const state = client.state;
    if (client.status !== "connected" || !state) {
        result.status = client.status === "incompatible" ? "Incompatible" : client.status === "connecting" ? "Connecting…" : "Offline";
        return result;
    }
    const binding = settings && dialBinding(settings, "rotate", 1, coarse ?? false);
    const feedback = keyFeedback(client, context, binding);
    result.icon = feedback.image;
    const mode = coarse !== undefined && (control === "position" || control === "marker")
        ? coarse ? "Coarse · 10 samples" : "Fine · 1 sample" : "";
    result.status = feedback.status === "inactive" || feedback.status === "active" ? "" : label(feedback.status);
    if (!state.availability.available) result.status = state.availability.reason.replaceAll("_", " ");
    else if (binding?.operation && state.controls[binding.operation]?.available === false) {
        const availability = state.controls[binding.operation];
        if (availability && !availability.available) result.status = availability.reason.replaceAll("_", " ");
    }
    result.status = [result.status, mode].filter(Boolean).join(" · ");
    switch (control) {
        case "library": {
            const library = state.library;
            result.value = library?.selected?.title ?? (library?.count === 0 ? "Empty Library" : "No selection");
            result.detail = library?.selected ? `${library.selected.index + 1}/${library.count} · Press: open` : `${library?.count ?? "—"} entries`;
            if (state.controls["library.open"]?.available === false) result.detail += " · Open unavailable";
            break;
        }
        case "position":
            result.value = state.playback?.position ? position(state.playback.position) : "—";
            result.detail = `${state.playback ? state.playback.playing ? "Playing" : "Paused" : "Unavailable"} · ${state.playback?.speed ?? "—"}×`;
            break;
        case "view":
            result.value = `${state.view?.start_seconds?.toFixed(2) ?? "—"}–${state.view?.end_seconds?.toFixed(2) ?? "—"} s`;
            result.detail = "Press: reset view";
            break;
        case "smoothing":
            result.value = `${state.view?.smoothing_window ?? "—"} samples`;
            result.detail = "Press: reset smoothing";
            break;
        case "speed":
            result.value = `${state.playback?.speed ?? "—"}×`;
            result.detail = `${state.playback ? state.playback.playing ? "Playing" : "Paused" : "Unavailable"} · Press: 1×`;
            break;
        case "marker": {
            const marker = state.markers.find(value => value.marker === settings?.marker);
            result.value = position(marker?.preview ?? marker?.applied);
            result.detail = `Applied ${position(marker?.applied)}`;
            const status = label(marker?.status ?? "unavailable");
            if (!result.status.startsWith(status)) result.status = [status, result.status].filter(Boolean).join(" · ");
            break;
        }
    }
    return result;
}

/** Neo feedback is contextual and display-only, including marker application and unavailable states. */
export function infoFeedback(client: ControlClient, settings: InfoSettings): Omit<SurfaceFeedback, "detail"> {
    const section = settings.section ?? "start";
    const control = section === "library" ? "library" : section === "view" ? "view"
        : section === "smoothing" ? "smoothing" : section === "speed" ? "speed" : settings.marker ? "marker" : "position";
    const dial: DialSettings = settings.marker ? { control: "marker", marker: settings.marker } : { control };
    const feedback = dialFeedback(client, "infobar", dial, undefined);
    const state = client.state;
    if (client.status === "connected" && state) {
        if (settings.marker) {
            feedback.status = `${feedback.status} · ${feedback.detail}`;
        } else if (section === "view") {
            feedback.title = state.curves.length === 0 ? "Curves"
                : state.curves.find(curve => curve.curve === "calibrated")?.active ? "Calibrated curves" : "Raw curves";
            feedback.value = state.curves.length === 0 ? "Unavailable"
                : state.curves.filter(curve => curve.active && curve.curve !== "calibrated").map(curve => curve.label).join(" · ") || "No visible curves";
        } else if (section === "markers") {
            const availability = state.controls["marker.preview"];
            const status: IconStatus = state.markers.some(marker => marker.status === "failed") ? "failed"
                : state.markers.some(marker => marker.status === "pending") ? "pending"
                : !state.availability.available || !availability?.available ? "unavailable" : "inactive";
            feedback.title = "Markers";
            feedback.value = "Start · Gravity · Incline · End";
            feedback.status = `${state.markers.filter(marker => marker.preview !== null).length} previews · ${label(status)}`;
            if (!state.availability.available) feedback.status += ` · ${state.availability.reason.replaceAll("_", " ")}`;
            else if (availability && !availability.available) feedback.status += ` · ${availability.reason.replaceAll("_", " ")}`;
            feedback.icon = keyImage("marker", status);
        } else if (["start", "explorer"].includes(section)) {
            feedback.title = section === "start" ? "Ride Forces Analyzer" : "Explorer";
            feedback.value = section === "start" ? "Library / Explorer" : "Playback / View / Markers";
            feedback.status = state.availability.available ? "Ready" : state.availability.reason.replaceAll("_", " ");
        } else {
            feedback.status = [feedback.status, feedback.detail].filter(Boolean).join(" · ");
            if (section === "playback") feedback.title = "Playback";
        }
    }
    return { icon: feedback.icon, title: feedback.title, value: feedback.value, status: feedback.status };
}
