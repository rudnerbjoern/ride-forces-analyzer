import type { ControlSettings } from "./controls.js";
import type { MarkerName, SelectionBoundary, Steps } from "./protocol.js";

export type DialControl = "library" | "position" | "view" | "smoothing" | "speed" | "marker" | "selection"
    | "zoom_selection" | "combined" | "playback" | "filter" | "display";
export type PlusMenu = "library" | "playback" | "curves" | "markers";
export type LibraryFilter = "park" | "status";
export type DialSettings = { control?: DialControl; marker?: MarkerName; boundary?: SelectionBoundary; filter?: LibraryFilter; menu?: PlusMenu; column?: 0 | 1 | 2 | 3 };
export type InfoSettings = { section?: string; marker?: MarkerName; boundary?: SelectionBoundary };

export type StepSize = 1 | 10 | 20;

/** Device-local step size survives menus, starts at one and never changes app state. */
export class StepMode {
    private readonly devices = new Map<string, StepSize>();
    private readonly listeners = new Set<() => void>();
    samples(device: string): StepSize { return this.devices.get(device) ?? 1; }
    toggle(device: string): void {
        const current = this.samples(device);
        this.devices.set(device, current === 1 ? 10 : current === 10 ? 20 : 1);
        for (const listener of this.listeners) listener();
    }
    subscribe(listener: () => void): void { this.listeners.add(listener); }
}

/** Validate profile settings before mapping a device gesture to an application command. */
export function dialSettings(value: DialSettings): DialSettings | undefined {
    if (!["library", "position", "view", "smoothing", "speed", "marker", "selection", "zoom_selection", "combined", "playback", "filter", "display"].includes(value.control ?? "")) return undefined;
    if (value.menu !== undefined && !["library", "playback", "curves", "markers"].includes(value.menu)) return undefined;
    if (value.column !== undefined && ![0, 1, 2, 3].includes(value.column)) return undefined;
    if (value.control === "filter" && value.filter !== "park" && value.filter !== "status") return undefined;
    if (value.control === "marker" && !["start", "gravity", "incline", "end"].includes(value.marker ?? "")) return undefined;
    if (value.control === "selection" && !["start", "end"].includes(value.boundary ?? "")) return undefined;
    return value;
}

/** Identify controls whose unused rotation and touch gestures must stay silent. */
export function isPressOnly(control: DialControl | undefined): boolean {
    return control === "zoom_selection" || control === "combined" || control === "playback";
}

/** One mapping shared by input handling and availability feedback; every tick remains a separate step. */
export function dialBinding(settings: DialSettings, gesture: "rotate" | "press" | "touch",
    direction: -1 | 1, stepSize: StepSize): ControlSettings | undefined {
    const control = settings.control;
    const steps = (direction * stepSize) as Steps;
    if (isPressOnly(control)) {
        if (gesture !== "press") return undefined;
        return control === "combined" ? { operation: "curve.set", curve: "combined" }
            : { operation: control === "playback" ? "playback.toggle" : "view.selection" };
    }
    if (control === "selection") {
        return gesture === "rotate" && settings.boundary ? { operation: "selection.step", boundary: settings.boundary, steps } : undefined;
    }
    if (control === "marker") {
        const marker = settings.marker;
        if (!marker) return undefined;
        return gesture === "rotate" ? { operation: "marker.preview", marker, steps }
            : { operation: gesture === "press" ? "marker.apply" : "marker.discard", marker };
    }
    if (gesture === "touch") return undefined;
    if (gesture === "press") {
        switch (control) {
            case "library": return { operation: "library.open" };
            case "position": return { operation: "playback.toggle" };
            case "view": return { operation: "view.reset" };
            case "smoothing": return { operation: "smoothing.reset" };
            case "speed": return { operation: "playback.speed.reset" };
            default: return undefined;
        }
    }
    switch (control) {
        case "library": return { operation: "library.move", direction };
        case "position": return { operation: "position.step", steps };
        case "view": return { operation: "view.zoom", direction };
        case "smoothing": return { operation: "smoothing.step", direction };
        case "speed": return { operation: "playback.speed.step", direction };
        default: return undefined;
    }
}
