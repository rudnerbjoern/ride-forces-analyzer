import { action, SingletonAction, type KeyAction, type KeyDownEvent, type WillAppearEvent,
    type WillDisappearEvent } from "@elgato/streamdeck";

import { StepMode } from "./device-controls.js";
import { imageData, keyImage } from "./feedback.js";

/** The 1/10/20-sample cycle is local to each Plus; marker presses remain Apply. */
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
                const samples = this.mode.samples(key.device.id);
                const state = samples === 1 ? 0 : samples === 10 ? 1 : 2;
                await key.setState(state);
                const label = samples === 1 ? "Fine" : samples === 10 ? "Medium" : "Coarse";
                const icon = samples === 1 ? "fine" : samples === 10 ? "medium" : "coarse";
                await key.setImage(imageData(keyImage(icon, samples === 1 ? "inactive" : "active")), { state });
                await key.setTitle(`${label}\n${samples} ${samples === 1 ? "sample" : "samples"}`);
            }
        });
        return this.rendering;
    }
}
