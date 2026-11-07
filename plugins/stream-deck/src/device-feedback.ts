import type { ControlClient } from "./client.js";
import { dialBinding, isPressOnly, type DialSettings, type StepSize, type InfoSettings } from "./device-controls.js";
import { keyFeedback, keyImage, unavailableLabel, type IconStatus } from "./feedback.js";
import type { Position } from "./protocol.js";

export type SurfaceFeedback = { icon: string; title: string; value: string; status: string; detail: string; visual: IconStatus };
const label = (value: string): string => value.charAt(0).toUpperCase() + value.slice(1);
const position = (value: Position | null | undefined): string => value ? `#${value.sample} · ${value.label}` : "Unset";

/** Touch-strip feedback uses only confirmed state and clearly separates previews from applied values. */
export function dialFeedback(client: ControlClient, context: string, settings: DialSettings | undefined,
    stepSize: StepSize | undefined, proposal?: string | null, showBadge = true): SurfaceFeedback {
    const control = settings?.control ?? "position";
    const pressOnly = isPressOnly(control);
    const title = control === "filter" ? `${settings?.filter === "park" ? "Park" : "Status"} · Touch: All`
        : control === "zoom_selection" ? "Zoom selection" : control === "playback" ? "Play/Pause"
        : control === "view" ? "Zoom" : control === "selection" ? `Selection ${settings?.boundary ?? "start"}`
        : label(control === "marker" ? settings?.marker ?? "Marker" : control);
    const symbol = control === "filter" ? settings?.filter === "park" ? "library" : "markers"
        : control === "zoom_selection" ? "selection" : control === "playback" && client.state?.playback?.playing ? "pause"
        : control === "selection" ? `selection_${settings?.boundary ?? "start"}`
        : control === "marker" ? settings?.marker ?? "marker" : control;
    const result: SurfaceFeedback = { icon: keyImage(symbol, "disconnected", true, showBadge), title, value: "—", status: "Offline", detail: "", visual: "disconnected" };
    if (pressOnly) result.detail = `Press: ${control === "combined" ? "toggle combined" : control === "playback" ? "play/pause" : "zoom selection"}`;
    const state = client.state;
    if (client.status !== "connected" || !state) {
        result.status = client.status === "incompatible" ? "Incompatible" : client.status === "connecting" ? "Connecting…" : "Offline";
        if (pressOnly) result.status += " · PRESS ONLY";
        return result;
    }
    if (control === "filter") {
        const filter = settings?.filter && state.library?.[`${settings.filter}_filter`];
        const active = filter?.options.find(option => option.value === filter.value);
        const choice = proposal === undefined ? active : filter?.options.find(option => option.value === proposal);
        const availability = state.controls["library.filter.set"];
        const blocked = !state.availability.available ? unavailableLabel(state.availability.reason)
            : availability?.available === false ? unavailableLabel(availability.reason)
            : !state.target || !choice || !availability ? "Unavailable" : "";
        const status: IconStatus = blocked ? "unavailable" : client.error(context) ? "failed"
            : client.pending(context) ? "pending" : proposal !== undefined ? "preview" : "active";
        result.value = choice?.label ?? "—";
        result.detail = `Active: ${active?.label ?? "—"}`;
        result.status = `${blocked || (status === "active" ? "Ready" : label(status))} · Press: Filter`;
        result.visual = status;
        result.icon = keyImage(symbol, status, true, showBadge);
        return result;
    }
    const binding = settings && dialBinding(settings, pressOnly ? "press" : "rotate", 1, stepSize ?? 1);
    const feedback = keyFeedback(client, context, binding);
    const marker = control === "marker" ? state.markers.find(value => value.marker === settings?.marker) : undefined;
    const mode = stepSize !== undefined && (control === "position" || control === "marker" || control === "selection")
        ? stepSize === 1 ? "Fine · 1 sample" : `${stepSize === 10 ? "Medium" : "Coarse"} · ${stepSize} samples` : "";
    const availability = binding?.operation ? state.controls[binding.operation] : undefined;
    const curveAvailability = control === "combined" ? state.curves.find(curve => curve.curve === "combined")?.availability : undefined;
    const blocked = !state.availability.available ? unavailableLabel(state.availability.reason)
        : availability?.available === false ? unavailableLabel(availability.reason)
        : curveAvailability?.available === false ? unavailableLabel(curveAvailability.reason)
        : marker?.availability.preview.available === false ? unavailableLabel(marker.availability.preview.reason)
        : feedback.status === "unavailable" ? "Unavailable" : "";
    let visual = feedback.status;
    let phase = "Ready";
    switch (control) {
        case "library": {
            const library = state.library;
            result.value = library?.selected?.title ?? (library?.count === 0 ? "Empty Library" : "No selection");
            result.detail = library?.selected ? `${library.selected.index + 1}/${library.count} · Press: open`
                : library ? `${library.count} entries` : "Library unavailable";
            if (state.controls["library.open"]?.available === false) result.detail += " · Open unavailable";
            break;
        }
        case "selection": {
            const boundary = settings?.boundary ?? "start";
            result.value = state.selection ? position(state.selection[boundary]) : "—";
            result.detail = state.selection ? `${boundary === "start" ? "End" : "Start"} ${position(state.selection[boundary === "start" ? "end" : "start"])}` : "No selection";
            break;
        }
        case "position":
            result.value = state.playback?.position ? position(state.playback.position) : "—";
            phase = state.playback ? state.playback.playing ? "Playing" : "Paused" : "Unavailable";
            result.detail = `${state.playback?.speed ?? "—"}× · Press: ${state.playback?.playing ? "pause" : "play"}`;
            if (state.playback?.playing && visual === "inactive") visual = "active";
            break;
        case "view": {
            const view = state.view;
            result.value = `${view?.start_seconds?.toFixed(2) ?? "—"}–${view?.end_seconds?.toFixed(2) ?? "—"} s`;
            phase = view?.start_seconds != null && view.end_seconds != null
                ? `Span ${(view.end_seconds - view.start_seconds).toFixed(2)} s` : "Unavailable";
            result.detail = "Press: reset view";
            break;
        }
        case "smoothing": {
            const raw = state.curves.find(curve => curve.curve === "calibrated")?.active === false;
            result.value = raw ? "Raw source values" : `${state.view?.smoothing_window ?? "—"} samples`;
            result.detail = raw ? "Select Calibrated" : "Press: reset smoothing";
            if (raw) phase = "Raw mode";
            break;
        }
        case "speed":
            result.value = `${state.playback?.speed ?? "—"}×`;
            phase = state.playback ? state.playback.playing ? "Playing" : "Paused" : "Unavailable";
            result.detail = "Press: 1×";
            if (state.playback?.playing && visual === "inactive") visual = "active";
            break;
        case "marker":
            result.value = position(marker?.preview ?? marker?.applied);
            result.detail = `Applied ${position(marker?.applied)}`;
            phase = label(marker?.status ?? "unavailable");
            if (marker?.status === "applied" && marker.applied && visual === "inactive") visual = "active";
            break;
        case "zoom_selection":
            result.value = state.selection ? `#${state.selection.start.sample}–${state.selection.end.sample}` : "—";
            break;
        case "combined": {
            const curve = state.curves.find(curve => curve.curve === "combined");
            result.value = curve ? curve.active ? "On" : "Off" : "—";
            break;
        }
        case "playback":
            result.value = state.playback ? state.playback.playing ? "Playing" : "Paused" : "—";
            break;
    }
    if (pressOnly) phase = "";
    if (feedback.status === "pending" || feedback.status === "failed") phase = label(feedback.status);
    if (blocked && phase === "Ready") phase = "";
    result.status = [phase, blocked, pressOnly ? "PRESS ONLY" : "", mode].filter((value, index, values) => value && values.indexOf(value) === index).join(" · ");
    result.visual = blocked ? "unavailable" : visual;
    result.icon = keyImage(symbol, result.visual, true, showBadge);
    return result;
}

/** Neo feedback is contextual and display-only, including marker application and unavailable states. */
export function infoFeedback(client: ControlClient, settings: InfoSettings): Pick<SurfaceFeedback, "icon" | "title" | "value" | "status"> {
    const section = settings.section ?? "start";
    const control = section === "library" ? "library" : section === "view" ? "view"
        : section === "smoothing" ? "smoothing" : section === "speed" ? "speed" : settings.marker ? "marker" : "position";
    const dial: DialSettings = settings.marker ? { control: "marker", marker: settings.marker } : { control };
    const feedback = dialFeedback(client, "infobar", dial, undefined);
    const state = client.state;
    if (["start", "explorer"].includes(section)) {
        feedback.title = section === "start" ? "Ride Forces Analyzer" : "Explorer";
        feedback.icon = keyImage("explorer", client.status === "connected" && state ? state.availability.available ? "inactive" : "unavailable" : "disconnected", true);
    }
    if (client.status === "connected" && state) {
        if (settings.marker) {
            const marker = state.markers.find(value => value.marker === settings.marker);
            const phase = marker?.status === "pending" || marker?.status === "failed" ? label(marker.status) : !state.availability.available ? unavailableLabel(state.availability.reason)
                : marker?.status ? label(marker.status) : "Unavailable";
            feedback.title = `${label(settings.marker)} · ${phase}`;
            feedback.status = feedback.detail;
        } else if (section === "view") {
            feedback.icon = keyImage("combined", !state.availability.available ? "unavailable" : "inactive", true);
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
            feedback.status = `${state.markers.filter(marker => marker.preview !== null).length} ${state.markers.filter(marker => marker.preview !== null).length === 1 ? "preview" : "previews"} · ${label(status)}`;
            if (!state.availability.available) feedback.status += ` · ${state.availability.reason.replaceAll("_", " ")}`;
            else if (availability && !availability.available) feedback.status += ` · ${availability.reason.replaceAll("_", " ")}`;
            feedback.icon = keyImage("marker", status, true);
        } else if (["start", "explorer"].includes(section)) {
            feedback.title = section === "start" ? "Ride Forces Analyzer" : "Explorer";
            feedback.value = section === "start" ? "Library / Explorer" : "Playback / Curves / Markers";
            feedback.status = state.availability.available ? "Ready" : state.availability.reason.replaceAll("_", " ");
        } else if (section === "library") {
            feedback.status = `${state.library?.selected ? `${state.library.selected.index + 1}/${state.library.count}` : `${state.library?.count ?? 0} entries`} · ${feedback.status}`;
        } else {
            if (["playback", "position"].includes(section)) feedback.status = `${feedback.status} · ${state.playback?.speed ?? "—"}×`;
            if (section === "playback") feedback.title = "Playback";
        }
    }
    return { icon: feedback.icon, title: feedback.title, value: feedback.value, status: feedback.status };
}
