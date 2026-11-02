import streamDeck, { action, SingletonAction, type KeyDownEvent } from "@elgato/streamdeck";

/** Return to the bundled device profile's first page without changing application state. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.home" })
export class HomeAction extends SingletonAction {
    constructor(private readonly switchProfile = streamDeck.profiles.switchToProfile) { super(); }

    override async onKeyDown(event: KeyDownEvent): Promise<void> {
        const device = event.action.device;
        const profile = device.type === 7 ? "profiles/plus" : device.type === 9 ? "profiles/neo" : undefined;
        if (!profile) { await event.action.showAlert(); return; }
        await this.switchProfile(device.id, profile, 0);
    }
}
