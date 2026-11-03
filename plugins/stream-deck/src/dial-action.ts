import { action, SingletonAction, type DialAction, type DialDownEvent, type DialRotateEvent,
    type DidReceiveSettingsEvent, type TouchTapEvent, type WillAppearEvent, type WillDisappearEvent } from "@elgato/streamdeck";

import type { ControlClient } from "./client.js";
import { requestedAction } from "./controls.js";
import { dialBinding, dialSettings, StepMode, type DialSettings } from "./device-controls.js";
import { dialFeedback } from "./device-feedback.js";
import { imageData } from "./feedback.js";

/** Shared Plus gesture handling; validation, bounds and analysis remain application-owned. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.dial" })
export class DialControlAction extends SingletonAction<DialSettings> {
    private readonly dials = new Map<string, { action: DialAction<DialSettings>; settings: DialSettings | undefined; signature?: string }>();
    private rendering = Promise.resolve();

    constructor(private readonly client: ControlClient, private readonly mode: StepMode) {
        super();
        const refresh = (): void => { void this.refresh().catch(error => console.error("Dial feedback failed", error)); };
        client.subscribe(refresh);
        mode.subscribe(refresh);
    }

    override async onWillAppear(event: WillAppearEvent<DialSettings>): Promise<void> {
        if (!event.action.isDial()) return;
        const settings = dialSettings(event.payload.settings);
        await event.action.setFeedbackLayout("layouts/plus.json");
        await event.action.setTriggerDescription({ rotate: settings?.control === "library" ? "Select one entry per notch" : "Adjust",
            push: settings?.control === "marker" ? "Apply this preview" : settings?.control === "library" ? "Open selection" : "Run assigned action",
            touch: settings?.control === "marker" ? "Discard this preview" : "" });
        this.dials.set(event.action.id, { action: event.action, settings });
        await this.refresh();
    }

    override onWillDisappear(event: WillDisappearEvent<DialSettings>): void { this.dials.delete(event.action.id); }

    override async onDidReceiveSettings(event: DidReceiveSettingsEvent<DialSettings>): Promise<void> {
        if (!event.action.isDial()) return;
        this.dials.set(event.action.id, { action: event.action, settings: dialSettings(event.payload.settings) });
        await this.refresh();
    }

    override async onDialRotate(event: DialRotateEvent<DialSettings>): Promise<void> {
        const ticks = event.payload.ticks;
        if (!Number.isSafeInteger(ticks) || ticks === 0) return;
        for (let index = 0; index < Math.abs(ticks); index++) {
            if (!this.invoke(event.action, event.payload.settings, "rotate", ticks < 0 ? -1 : 1)) {
                await event.action.showAlert();
                break;
            }
        }
    }

    override async onDialDown(event: DialDownEvent<DialSettings>): Promise<void> {
        if (event.payload.settings.control === "selection") return;
        if (!this.invoke(event.action, event.payload.settings, "press", 1)) await event.action.showAlert();
    }

    override async onTouchTap(event: TouchTapEvent<DialSettings>): Promise<void> {
        // The whole field discards only its associated marker; other fields have no touch command.
        if (event.payload.settings.control !== "marker") return;
        if (!this.invoke(event.action, event.payload.settings, "touch", 1)) await event.action.showAlert();
    }

    private invoke(action_: DialAction<DialSettings>, value: DialSettings, gesture: "rotate" | "press" | "touch",
        direction: -1 | 1): boolean {
        const settings = dialSettings(value);
        const binding = settings && dialBinding(settings, gesture, direction, this.mode.coarse(action_.device.id));
        const requested = binding && requestedAction(binding, this.client.state);
        return requested !== undefined && this.client.send(action_.id, requested);
    }

    private refresh(): Promise<void> {
        this.rendering = this.rendering.catch(() => {}).then(async () => {
            for (const [context, dial] of this.dials) {
                const feedback = dialFeedback(this.client, context, dial.settings, this.mode.coarse(dial.action.device.id));
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
