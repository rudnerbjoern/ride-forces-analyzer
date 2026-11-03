import type { ControlSettings } from "./controls.js";
import type { MarkerName } from "./protocol.js";

export type DialControl = "library" | "position" | "view" | "smoothing" | "speed" | "marker";
export type DialSettings = { control?: DialControl; marker?: MarkerName };
export type InfoSettings = { section?: string; marker?: MarkerName };

/** Device-local fine/coarse mode survives menus, defaults to fine and never changes app state. */
export class StepMode {
    private readonly coarseDevices = new Set<string>();
    private readonly listeners = new Set<() => void>();
    coarse(device: string): boolean { return this.coarseDevices.has(device); }
    toggle(device: string): void {
        if (!this.coarseDevices.delete(device)) this.coarseDevices.add(device);
        for (const listener of this.listeners) listener();
    }
    subscribe(listener: () => void): void { this.listeners.add(listener); }
}

/** Validate profile settings before mapping a device gesture to an application command. */
export function dialSettings(value: DialSettings): DialSettings | undefined {
    if (!["library", "position", "view", "smoothing", "speed", "marker"].includes(value.control ?? "")) return undefined;
    if (value.control === "marker" && !["start", "gravity", "incline", "end"].includes(value.marker ?? "")) return undefined;
    return value;
}

/** One mapping shared by input handling and availability feedback; every tick remains a separate step. */
export function dialBinding(settings: DialSettings, gesture: "rotate" | "press" | "touch",
    direction: -1 | 1, coarse: boolean): ControlSettings | undefined {
    const control = settings.control;
    const steps = coarse ? direction === -1 ? -10 : 10 : direction;
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
