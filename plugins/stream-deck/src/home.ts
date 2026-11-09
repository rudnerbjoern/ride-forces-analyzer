import streamDeck, { action, type KeyDownEvent, SingletonAction } from "@elgato/streamdeck";

import { logFailure } from "./diagnostics.js";
import { profilePath } from "./localization.js";

/** Return to the bundled device profile's first page without changing application state. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.home" })
export class HomeAction extends SingletonAction {
	/**
	 * Use the SDK profile switcher for native Home navigation.
	 * @param switchProfile SDK function returning the invoking device to the bundled profile.
	 */
	constructor(private readonly switchProfile = streamDeck.profiles.switchToProfile) {
		super();
	}

	/**
	 * Handle a key press from the invoking device.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onKeyDown(event: KeyDownEvent): Promise<void> {
		const device = event.action.device;
		const profile = device.type === 7 ? profilePath("plus") : device.type === 9 ? profilePath("neo") : undefined;
		if (!profile) {
			await event.action.showAlert();
			return;
		}
		try {
			await this.switchProfile(device.id, profile, 0);
		} catch (error) {
			logFailure("Home page request failed", error, "warn");
			await event.action.showAlert();
		}
	}
}
