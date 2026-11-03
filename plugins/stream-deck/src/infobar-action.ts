import { action, SingletonAction, type DidReceiveSettingsEvent, type NeoInfobarAction,
    type WillAppearEvent, type WillDisappearEvent } from "@elgato/streamdeck";

import type { ControlClient } from "./client.js";
import type { InfoSettings } from "./device-controls.js";
import { infoFeedback } from "./device-feedback.js";

/** Contextual Neo display; intentionally has no input handlers or command path. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.infobar" })
export class InfoBarAction extends SingletonAction<InfoSettings> {
    private readonly bars = new Map<string, { action: NeoInfobarAction<InfoSettings>; settings: InfoSettings; signature?: string }>();
    private rendering = Promise.resolve();
    constructor(private readonly client: ControlClient) {
        super();
        client.subscribe(() => { void this.refresh().catch(error => console.error("InfoBar feedback failed", error)); });
    }
    override async onWillAppear(event: WillAppearEvent<InfoSettings>): Promise<void> {
        if (!event.action.isNeoInfobar()) return;
        await event.action.setFeedbackLayout("layouts/neo.json");
        this.bars.set(event.action.id, { action: event.action, settings: event.payload.settings });
        await this.refresh();
    }
    override onWillDisappear(event: WillDisappearEvent<InfoSettings>): void { this.bars.delete(event.action.id); }
    override async onDidReceiveSettings(event: DidReceiveSettingsEvent<InfoSettings>): Promise<void> {
        if (!event.action.isNeoInfobar()) return;
        this.bars.set(event.action.id, { action: event.action, settings: event.payload.settings });
        await this.refresh();
    }
    private refresh(): Promise<void> {
        this.rendering = this.rendering.catch(() => {}).then(async () => {
            for (const bar of this.bars.values()) {
                const feedback = infoFeedback(this.client, bar.settings);
                const signature = JSON.stringify(feedback);
                if (signature === bar.signature) continue;
                await bar.action.setFeedback(feedback);
                bar.signature = signature;
            }
        });
        return this.rendering;
    }
}
