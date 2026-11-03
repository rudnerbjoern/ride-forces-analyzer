import { action, SingletonAction, type KeyAction, type KeyDownEvent, type WillAppearEvent,
    type WillDisappearEvent } from "@elgato/streamdeck";

import { StepMode } from "./device-controls.js";
import { keyImage } from "./feedback.js";

/** Fine/Coarse is local to each Plus; marker presses remain Apply. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.step-mode" })
export class StepModeAction extends SingletonAction {
    private readonly keys = new Map<string, KeyAction<{}>>();
    private rendering = Promise.resolve();
    constructor(private readonly mode: StepMode) {
        super();
        mode.subscribe(() => { void this.refresh().catch(error => console.error("Step mode feedback failed", error)); });
    }
    override async onWillAppear(event: WillAppearEvent): Promise<void> {
        if (!event.action.isKey()) return;
        this.keys.set(event.action.id, event.action);
        await this.refresh();
    }
    override onWillDisappear(event: WillDisappearEvent): void { this.keys.delete(event.action.id); }
    override async onKeyDown(event: KeyDownEvent): Promise<void> {
        this.mode.toggle(event.action.device.id);
        await this.refresh();
    }
    private refresh(): Promise<void> {
        this.rendering = this.rendering.catch(() => {}).then(async () => {
            for (const key of this.keys.values()) {
                const coarse = this.mode.coarse(key.device.id);
                await key.setState(coarse ? 1 : 0);
                await key.setImage(keyImage("position", coarse ? "active" : "inactive"));
                await key.setTitle(coarse ? "Coarse\n10 samples" : "Fine\n1 sample");
            }
        });
        return this.rendering;
    }
}
