import streamDeck, { action, SingletonAction, type KeyAction, type KeyDownEvent,
    type WillAppearEvent, type WillDisappearEvent } from "@elgato/streamdeck";

import { imageData, keyImage, keyTitle, type IconStatus } from "./feedback.js";
import type { ControlClient } from "./client.js";

export const PLUS_PAGES = [
    { id: "library", name: "Library", group: "library" },
    { id: "playback", name: "Playback / Navigate", group: "playback" },
    { id: "selection", name: "Playback / Selection", group: "playback" },
    { id: "curves", name: "Curves", group: "curves" },
    { id: "markers", name: "Markers / Markers", group: "markers" },
    { id: "marker-view", name: "Markers / View", group: "markers" },
] as const;
export type PlusPage = 0 | 1 | 2 | 3 | 4 | 5;
type Group = typeof PLUS_PAGES[number]["group"];
export type NavigationSettings = { page: PlusPage; target: Group | 1 | 2 | 4 | 5 };

/** Admit only the fixed Plus menu and its own subgroup keys. */
export function navigationSettings(value: Record<string, unknown>): NavigationSettings | undefined {
    if (typeof value.page !== "number" || !Number.isInteger(value.page) || value.page < 0 || value.page > 5) return undefined;
    const group = PLUS_PAGES[value.page]?.group;
    if (!["library", "playback", "curves", "markers"].includes(value.target as string)
        && !(group === "playback" && (value.target === 1 || value.target === 2))
        && !(group === "markers" && (value.target === 4 || value.target === 5))) return undefined;
    return { page: value.page as PlusPage, target: value.target as NavigationSettings["target"] };
}

/** Draw cyan local selection only for the page confirmed by an appearance event. */
export function navigationFeedback(settings: NavigationSettings, confirmed: PlusPage | undefined,
    client?: Pick<ControlClient, "state" | "status">): {
    title: string; image: string; selected: boolean;
} {
    const target = settings.target;
    let title = typeof target === "string" ? { library: "Library", playback: "Playback", curves: "Curves", markers: "Markers" }[target]
        : { 1: "Navigate", 2: "Selection", 4: "Markers", 5: "View" }[target];
    const symbol = target === "curves" ? "combined" : target === 1 ? "position" : target === 2 ? "selection"
        : target === 4 ? "markers" : target === 5 ? "view" : target;
    const selected = confirmed !== undefined && (typeof target === "string" ? PLUS_PAGES[confirmed].group === target : confirmed === target);
    let status: IconStatus | undefined;
    if (typeof target === "string") {
        let caption: string;
        const state = client?.state;
        if (client?.status !== "connected" || !state) {
            caption = client?.status === "connecting" ? "Connecting…" : client?.status === "incompatible" ? "Version err" : "Offline";
            status = "disconnected";
        } else if (target === "library") {
            const library = state.library;
            caption = library?.selected ? `${library.selected.index + 1}/${library.count}`
                : library ? library.count === 0 ? "Empty" : `—/${library.count}` : "No Explorer";
        } else if (target === "playback") {
            caption = state.playback ? state.playback.playing ? "Playing" : "Paused" : "No data";
        } else if (target === "curves") {
            const mode = state.curves.find(curve => curve.curve === "calibrated");
            caption = mode ? mode.active ? "Calibrated" : "Raw" : "No data";
        } else {
            const previews = state.markers.filter(marker => marker.preview !== null).length;
            status = state.markers.some(marker => marker.status === "failed") ? "failed"
                : state.markers.some(marker => marker.status === "pending") ? "pending"
                : previews > 0 ? "preview" : undefined;
            caption = status === "failed" ? "Failed" : status === "pending" ? "Pending"
                : previews > 0 ? `${previews} ${previews === 1 ? "preview" : "previews"}`
                : state.markers.length === 0 ? "No data" : "No preview";
        }
        title = keyTitle(`${title}\n${caption}`);
    }
    const image = keyImage(symbol, status).replace("</svg>", selected
        ? '<rect x="2" y="2" width="140" height="140" rx="16" fill="none" stroke="#64d6ff" stroke-width="3"/>'
            + '<path d="M16 136h112" stroke="#64d6ff" stroke-width="3"/></svg>' : "</svg>");
    return { title, image, selected };
}

/** Switch only the invoking Plus; remember subgroups from confirmed appearances. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.plus-navigation" })
export class PlusNavigationAction extends SingletonAction<NavigationSettings> {
    private readonly devices = new Map<string, { page: PlusPage | undefined; playback: 1 | 2; markers: 4 | 5 }>();
    private readonly keys = new Map<string, { action: KeyAction<NavigationSettings>; settings: NavigationSettings; signature?: string }>();
    private readonly sending = new Set<string>();
    private rendering = Promise.resolve();

    constructor(private readonly client: ControlClient, private readonly switchProfile = streamDeck.profiles.switchToProfile) {
        super();
        client.subscribe(() => { void this.refresh().catch(error => console.error("Plus menu feedback failed", error)); });
    }

    override async onWillAppear(event: WillAppearEvent<NavigationSettings>): Promise<void> {
        const settings = navigationSettings(event.payload.settings);
        if (event.action.device.type !== 7 || !event.action.isKey() || !settings) return;
        const device = this.device(event.action.device.id);
        if (device.page !== settings.page) streamDeck.logger.info("Plus page appeared", { device: event.action.device.id, page: settings.page });
        device.page = settings.page;
        if (settings.page === 1 || settings.page === 2) device.playback = settings.page;
        if (settings.page === 4 || settings.page === 5) device.markers = settings.page;
        this.keys.set(event.action.id, { action: event.action, settings });
        await this.refresh();
    }

    override onWillDisappear(event: WillDisappearEvent<NavigationSettings>): void {
        this.keys.delete(event.action.id);
        if (![...this.keys.values()].some(key => key.action.device.id === event.action.device.id)) {
            this.device(event.action.device.id).page = undefined;
        }
    }

    override async onKeyDown(event: KeyDownEvent<NavigationSettings>): Promise<void> {
        const settings = navigationSettings(event.payload.settings);
        if (event.action.device.type !== 7 || !settings) { await event.action.showAlert(); return; }
        const id = event.action.device.id;
        const device = this.device(id);
        const target = settings.target;
        const page = target === "library" ? 0 : target === "curves" ? 3
            : target === "playback" ? device.playback : target === "markers" ? device.markers : target;
        if (page === device.page || this.sending.has(id)) return;
        this.sending.add(id);
        try {
            await this.switchProfile(id, "profiles/plus", page);
            streamDeck.logger.info("Plus page request sent", { device: id, page });
        } catch (error) {
            streamDeck.logger.warn("Plus page request failed", error);
            await event.action.showAlert();
        } finally {
            this.sending.delete(id);
        }
    }

    private device(id: string) {
        let state = this.devices.get(id);
        if (!state) {
            state = { page: undefined, playback: 1, markers: 4 };
            this.devices.set(id, state);
        }
        return state;
    }

    private refresh(): Promise<void> {
        this.rendering = this.rendering.catch(() => {}).then(async () => {
            for (const key of this.keys.values()) {
                const feedback = navigationFeedback(key.settings, this.device(key.action.device.id).page, this.client);
                const signature = JSON.stringify(feedback);
                if (signature === key.signature) continue;
                await key.action.setState(feedback.selected ? 1 : 0);
                await key.action.setImage(imageData(feedback.image), { state: feedback.selected ? 1 : 0 });
                await key.action.setTitle(feedback.title);
                key.signature = signature;
            }
        });
        return this.rendering;
    }
}
