import { action, SingletonAction, type DidReceiveSettingsEvent, type KeyAction, type KeyDownEvent,
    type WillAppearEvent, type WillDisappearEvent } from "@elgato/streamdeck";

import { ControlClient } from "./client.js";
import { controlSettings, requestedAction, type ControlSettings } from "./controls.js";
import { keyFeedback } from "./feedback.js";

/** One configurable key action; folders, dials and device profiles have separate implementation steps. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.control" })
export class ControlAction extends SingletonAction<ControlSettings> {
    private readonly keys = new Map<string, { action: KeyAction<ControlSettings>; settings: ControlSettings | undefined; signature?: string }>();
    private rendering = Promise.resolve();

    constructor(private readonly client: ControlClient) {
        super();
        client.subscribe(() => { void this.refresh().catch(error => console.error("Stream Deck feedback failed", error)); });
    }

    override async onWillAppear(event: WillAppearEvent<ControlSettings>): Promise<void> {
        if (!event.action.isKey()) return;
        this.keys.set(event.action.id, { action: event.action, settings: controlSettings(event.payload.settings) });
        await this.refresh();
    }

    override onWillDisappear(event: WillDisappearEvent<ControlSettings>): void {
        this.keys.delete(event.action.id);
    }

    override async onDidReceiveSettings(event: DidReceiveSettingsEvent<ControlSettings>): Promise<void> {
        if (!event.action.isKey()) return;
        this.keys.set(event.action.id, { action: event.action, settings: controlSettings(event.payload.settings) });
        await this.refresh();
    }

    override async onKeyDown(event: KeyDownEvent<ControlSettings>): Promise<void> {
        const settings = controlSettings(event.payload.settings);
        const requested = settings && requestedAction(settings, this.client.state);
        if (!requested || !this.client.send(event.action.id, requested)) await event.action.showAlert();
    }

    private refresh(): Promise<void> {
        this.rendering = this.rendering.catch(() => {}).then(async () => {
            for (const [context, key] of this.keys) {
                const feedback = keyFeedback(this.client, context, key.settings);
                const signature = JSON.stringify(feedback);
                if (signature === key.signature) continue;
                await key.action.setState(feedback.state);
                await key.action.setImage(feedback.image);
                await key.action.setTitle(feedback.title);
                key.signature = signature;
            }
        });
        return this.rendering;
    }
}
