import type { ControlClient } from "./client.js";
import { CONTROL_LABELS, requestedAction, type ControlSettings } from "./controls.js";

export type IconStatus = "active" | "inactive" | "unavailable" | "pending" | "failed" | "disconnected";
export interface KeyFeedback {
    title: string;
    image: string;
    state: 0 | 1;
}

const paths = {
    library: "M35 30h32v64H35z M77 30h32v64H77z M45 43h12 M87 43h12",
    playback: "M52 30l43 32-43 32z",
    pause: "M50 30v64 M90 30v64",
    speed: "M30 90a45 45 0 1 1 84 0 M72 72l26-31 M39 52l8 5 M72 28v10 M105 52l-8 5",
    position: "M35 62h74 M50 47L35 62l15 15 M94 47l15 15-15 15",
    view: "M85 81l23 23 M93 57a30 30 0 1 0-60 0 30 30 0 0 0 60 0 M46 57h34 M63 40v34",
    smoothing: "M27 65c15-48 23 48 40 0s25 48 50 0",
    curve: "M28 80l20-30 20 22 22-44 26 22",
    marker: "M46 104V26l54 22-54 22",
};

/** Generate vector feedback with a distinct availability badge and no external resources. */
export function keyImage(area: string, status: IconStatus, playing = false): string {
    const color = { active: "#52dc96", inactive: "#e2e8f0", unavailable: "#f6bd4f",
        pending: "#62b5ff", failed: "#ff7777", disconnected: "#8290a6" }[status];
    const shape = playing ? paths.pause : paths[area as keyof typeof paths] ?? paths.playback;
    const badge = status === "unavailable" || status === "failed" ? '<path d="M116 108v9m0 5v1"/>'
        : status === "pending" ? '<path d="M116 106v10l6 4"/>'
        : status === "disconnected" ? '<path d="M108 108l16 16m0-16-16 16"/>'
        : '<path d="M108 116l6 6 10-14"/>';
    return `<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">`
        + `<rect width="144" height="144" rx="16" fill="#172338"/>`
        + `<g stroke="${color}" fill="none" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">`
        + `<g transform="translate(20 -4) scale(.72)"><path d="${shape}"/></g>`
        + `<g transform="translate(0 -96)"><circle cx="116" cy="116" r="19" fill="#172338"/>${badge}</g></g></svg>`;
}

/** Render values and toggles from app snapshots, never from a successful button press alone. */
export function keyFeedback(client: ControlClient, context: string, settings: ControlSettings | undefined): KeyFeedback {
    const name = settings?.operation ?? "playback.toggle";
    const area = name.startsWith("playback.speed") ? "speed" : name.split(".")[0] ?? "playback";
    const label = settings ? CONTROL_LABELS[name] : "Choose action";
    const snapshot = client.state;
    let title = label;
    let active = false;
    let playing = false;
    let status: IconStatus = "inactive";
    if (client.status !== "connected" || !snapshot) {
        const detail = client.status === "incompatible" ? "Incompatible" : client.status === "connecting" ? "Connecting…" : "Offline";
        return { title: `${label}\n${detail}`, image: keyImage(area, "disconnected"), state: 0 };
    }
    if (name.startsWith("library.")) {
        const selected = snapshot.library?.selected;
        title = name === "library.import" ? "Import…" : name === "library.open" ? `Open\n${selected?.title.slice(0, 24) ?? "No selection"}`
            : `${selected?.title.slice(0, 20) ?? "Library"}\n${settings?.direction === -1 ? "↑" : "↓"} ${selected ? `${selected.index + 1}/${snapshot.library?.count}` : snapshot.library ? snapshot.library.count === 0 ? "Empty" : "No selection" : "—"}`;
    } else if (name === "playback.toggle") {
        playing = snapshot.playback?.playing ?? false;
        active = playing;
        title = `${playing ? "Pause" : "Play"}\n${snapshot.playback?.speed ?? "—"}×`;
    } else if (name.startsWith("playback.speed")) {
        title = `${name.endsWith("reset") ? "Reset speed" : `Speed ${settings?.direction === -1 ? "−" : "+"}`}\n${snapshot.playback?.speed ?? "—"}×`;
    } else if (name === "position.step") {
        title = `Position ${settings?.steps ?? 1}\n${snapshot.playback?.position?.label ?? "—"}`;
    } else if (name.startsWith("smoothing.")) {
        title = `${name.endsWith("reset") ? "Reset smooth" : `Smooth ${settings?.direction === -1 ? "−" : "+"}`}\n${snapshot.view?.smoothing_window ?? "—"} samples`;
    } else if (name === "view.zoom") {
        title = `Zoom ${settings?.direction === -1 ? "−" : "+"}\n${snapshot.view?.start_seconds?.toFixed(1) ?? "—"}–${snapshot.view?.end_seconds?.toFixed(1) ?? "—"} s`;
    } else if (name === "curve.set") {
        const curve = snapshot.curves.find(value => value.curve === (settings?.curve ?? "first"));
        active = curve?.active ?? false;
        title = `${curve?.label ?? "Curve"}\n${active ? "On" : "Off"}`;
    } else if (name.startsWith("marker.")) {
        const marker = snapshot.markers.find(value => value.marker === (settings?.marker ?? "start"));
        const value = marker?.preview ?? marker?.applied;
        const verb = name === "marker.preview" ? `Step ${settings?.steps ?? 1}` : name === "marker.apply" ? "Apply" : "Discard";
        title = `${marker?.marker ?? "Marker"} ${verb}\n${value?.label ?? "Unset"}`;
        if (marker?.status === "pending") status = "pending";
        if (marker?.status === "failed") status = "failed";
        if (marker?.status === "preview") title += "\nPreview";
    }
    if (active) status = "active";
    if ((!settings || !requestedAction(settings, snapshot)) && status !== "pending" && status !== "failed") {
        status = "unavailable";
        title += `\n${snapshot.availability.available ? "Unavailable" : snapshot.availability.reason.replaceAll("_", " ")}`;
    }
    if (client.pending(context)) status = "pending";
    if (client.error(context)) status = "failed";
    if (status === "pending") title += "\nPending";
    if (status === "failed") title += "\nFailed";
    return { title, image: keyImage(area, status, playing), state: active ? 1 : 0 };
}
