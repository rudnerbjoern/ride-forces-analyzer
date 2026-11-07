import { action, SingletonAction, type DialAction, type DialDownEvent, type DialRotateEvent,
    type DidReceiveSettingsEvent, type TouchTapEvent, type WillAppearEvent, type WillDisappearEvent } from "@elgato/streamdeck";

import { sameTarget, type ControlClient } from "./client.js";
import { requestedAction } from "./controls.js";
import { dialBinding, dialSettings, isPressOnly, StepMode, type DialSettings, type LibraryFilter } from "./device-controls.js";
import { dialFeedback } from "./device-feedback.js";
import { imageData } from "./feedback.js";

/** Shared Plus gesture handling; validation, bounds and analysis remain application-owned. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.dial" })
export class DialControlAction extends SingletonAction<DialSettings> {
    private readonly dials = new Map<string, { action: DialAction<DialSettings>; settings: DialSettings | undefined; signature?: string }>();
    private rendering = Promise.resolve();
    private readonly proposals = new Map<string, Map<LibraryFilter, string | null>>();
    private previous: ControlClient["state"];

    constructor(private readonly client: ControlClient, private readonly mode: StepMode) {
        super();
        this.previous = client.state;
        const refresh = (): void => { void this.refresh().catch(error => console.error("Dial feedback failed", error)); };
        client.subscribe(() => { this.synchronizeFilters(); refresh(); });
        mode.subscribe(refresh);
    }

    override async onWillAppear(event: WillAppearEvent<DialSettings>): Promise<void> {
        if (!event.action.isDial()) return;
        const settings = dialSettings(event.payload.settings);
        await event.action.setFeedbackLayout("layouts/plus.json");
        await event.action.setTriggerDescription({ rotate: isPressOnly(settings?.control) ? "" : settings?.control === "library" ? "Select one entry per notch" : "Adjust",
            push: settings?.control === "filter" ? "Filter" : settings?.control === "selection" ? "" : settings?.control === "marker" ? "Apply this preview" : settings?.control === "library" ? "Open selection" : "Run assigned action",
            touch: settings?.control === "filter" ? "Reset this filter to All" : settings?.control === "marker" ? "Discard this preview" : "" });
        this.dials.set(event.action.id, { action: event.action, settings });
        await this.refresh();
    }

    override onWillDisappear(event: WillDisappearEvent<DialSettings>): void {
        const filter = this.dials.get(event.action.id)?.settings?.filter;
        if (filter) this.proposals.get(event.action.device.id)?.delete(filter);
        this.dials.delete(event.action.id);
    }

    override async onDidReceiveSettings(event: DidReceiveSettingsEvent<DialSettings>): Promise<void> {
        if (!event.action.isDial()) return;
        this.resetFilters(event.action.device.id);
        this.dials.set(event.action.id, { action: event.action, settings: dialSettings(event.payload.settings) });
        await this.refresh();
    }

    override async onDialRotate(event: DialRotateEvent<DialSettings>): Promise<void> {
        if (isPressOnly(dialSettings(event.payload.settings)?.control)) return;
        const ticks = event.payload.ticks;
        if (!Number.isSafeInteger(ticks) || ticks === 0) return;
        const settings = dialSettings(event.payload.settings);
        if (settings?.control === "filter") {
            if (!this.filterGesture(event.action, settings.filter!, "rotate", ticks)) await event.action.showAlert();
            return;
        }
        for (let index = 0; index < Math.abs(ticks); index++) {
            if (!this.invoke(event.action, event.payload.settings, "rotate", ticks < 0 ? -1 : 1)) {
                await event.action.showAlert();
                break;
            }
        }
    }

    override async onDialDown(event: DialDownEvent<DialSettings>): Promise<void> {
        const settings = dialSettings(event.payload.settings);
        if (settings?.control === "filter") {
            if (!this.filterGesture(event.action, settings.filter!, "press")) await event.action.showAlert();
            return;
        }
        if (event.payload.settings.control === "selection") return;
        if (!this.invoke(event.action, event.payload.settings, "press", 1)) await event.action.showAlert();
    }

    override async onTouchTap(event: TouchTapEvent<DialSettings>): Promise<void> {
        const settings = dialSettings(event.payload.settings);
        if (settings?.control === "filter") {
            if (!this.filterGesture(event.action, settings.filter!, "touch")) await event.action.showAlert();
            return;
        }
        // Marker touch discards only its associated preview; other fields have no touch command.
        if (event.payload.settings.control !== "marker") return;
        if (!this.invoke(event.action, event.payload.settings, "touch", 1)) await event.action.showAlert();
    }

    /** Discard this device's proposals, including when Reset filters cannot be sent. */
    resetFilters(device: string): void {
        this.proposals.delete(device);
        void this.refresh().catch(error => console.error("Filter feedback failed", error));
    }

    private synchronizeFilters(): void {
        const state = this.client.state;
        if (!state || state.session_id !== this.previous?.session_id || !sameTarget(state.target, this.previous?.target ?? null)) {
            this.proposals.clear();
        } else {
            for (const filter of ["park", "status"] as const) {
                if (JSON.stringify(state.library?.[`${filter}_filter`]) !== JSON.stringify(this.previous?.library?.[`${filter}_filter`])) {
                    for (const proposals of this.proposals.values()) proposals.delete(filter);
                }
            }
        }
        this.previous = state;
    }

    private filterGesture(action_: DialAction<DialSettings>, filter: LibraryFilter,
        gesture: "rotate" | "press" | "touch", ticks = 0): boolean {
        // A late event from a vanished page must not operate on the current target.
        if (this.dials.get(action_.id)?.settings?.filter !== filter) return false;
        const device = action_.device.id;
        if (gesture === "touch") {
            this.proposals.get(device)?.delete(filter);
            void this.refresh().catch(error => console.error("Filter feedback failed", error));
        }
        const state = this.client.state;
        const choices = state?.library?.[`${filter}_filter`];
        if (this.client.status !== "connected" || !state?.target || !state.availability.available
            || !state.controls["library.filter.set"]?.available || !choices?.options.length) return false;
        const proposals = this.proposals.get(device) ?? new Map<LibraryFilter, string | null>();
        const value = proposals.has(filter) ? proposals.get(filter)! : choices.value;
        const index = choices.options.findIndex(option => option.value === value);
        if (index < 0) return false;
        if (gesture === "rotate") {
            const next = choices.options[Math.max(0, Math.min(choices.options.length - 1, index + ticks))]!.value;
            if (next === choices.value) proposals.delete(filter);
            else proposals.set(filter, next);
            this.proposals.set(device, proposals);
            void this.refresh().catch(error => console.error("Filter feedback failed", error));
            return true;
        }
        const requested = gesture === "touch" ? null : value;
        if (!choices.options.some(option => option.value === requested)) return false;
        return this.client.send(action_.id, { name: "library.filter.set", filter, value: requested });
    }

    private invoke(action_: DialAction<DialSettings>, value: DialSettings, gesture: "rotate" | "press" | "touch",
        direction: -1 | 1): boolean {
        const settings = dialSettings(value);
        const binding = settings && dialBinding(settings, gesture, direction, this.mode.samples(action_.device.id));
        const requested = binding && requestedAction(binding, this.client.state);
        return requested !== undefined && this.client.send(action_.id, requested);
    }

    private refresh(): Promise<void> {
        this.rendering = this.rendering.catch(() => {}).then(async () => {
            for (const [context, dial] of this.dials) {
                const proposal = dial.settings?.filter ? this.proposals.get(dial.action.device.id)?.get(dial.settings.filter) : undefined;
                const feedback = dialFeedback(this.client, context, dial.settings, this.mode.samples(dial.action.device.id), proposal);
                const signature = JSON.stringify(feedback);
                if (signature === dial.signature) continue;
                const icon = imageData(feedback.icon);
                await dial.action.setImage(icon);
                await dial.action.setFeedback({ ...feedback, icon });
                dial.signature = signature;
            }
        });
        return this.rendering;
    }
}
