import {
	action,
	type DidReceiveSettingsEvent,
	type KeyAction,
	type KeyDownEvent,
	SingletonAction,
	type WillAppearEvent,
	type WillDisappearEvent,
} from "@elgato/streamdeck";

import { ControlClient } from "./client.js";
import { controlSettings, type ControlSettings, requestedAction } from "./controls.js";
import { logFailure } from "./diagnostics.js";
import { FeedbackScheduler } from "./feedback-scheduler.js";
import { imageData, keyFeedback } from "./feedback.js";

/** One configurable application key action, independent of native folder navigation. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.control" })
export class ControlAction extends SingletonAction<ControlSettings> {
	/**
	 *
	 */
	private readonly keys = new Map<
		string,
		{
			/**
			 *
			 */
			action: KeyAction<ControlSettings>;
			/**
			 *
			 */
			settings: ControlSettings | undefined;
		}
	>();
	/**
	 *
	 */
	private readonly rendering = new FeedbackScheduler();

	/**
	 * Connect visible application keys to the shared confirmed-state client.
	 * @param client Shared Analyzer client supplying state and command routing.
	 * @param resetFilters Optional callback discarding this device's unconfirmed filter choices.
	 */
	constructor(
		private readonly client: ControlClient,
		private readonly resetFilters?: (device: string) => void,
	) {
		super();
		client.subscribe((failedContext) => {
			const key = failedContext === undefined ? undefined : this.keys.get(failedContext);
			if (key) void key.action.showAlert().catch((error) => logFailure("Stream Deck alert failed", error));
			void this.refresh().catch((error) => logFailure("Stream Deck feedback failed", error));
		});
	}

	/**
	 * Update the visible action after its saved settings change.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onDidReceiveSettings(event: DidReceiveSettingsEvent<ControlSettings>): Promise<void> {
		if (!event.action.isKey()) return;
		this.keys.set(event.action.id, { action: event.action, settings: controlSettings(event.payload.settings) });
		await this.refresh();
	}

	/**
	 * Handle a key press from the invoking device.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onKeyDown(event: KeyDownEvent<ControlSettings>): Promise<void> {
		const settings = controlSettings(event.payload.settings);
		if (settings?.operation === "library.filter.reset") this.resetFilters?.(event.action.device.id);
		const requested = settings && requestedAction(settings, this.client.state);
		if (!requested || !this.client.send(event.action.id, requested)) await event.action.showAlert();
	}

	/**
	 * Register the visible action and refresh its confirmed feedback.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onWillAppear(event: WillAppearEvent<ControlSettings>): Promise<void> {
		if (!event.action.isKey()) return;
		this.rendering.forget(event.action.id);
		this.keys.set(event.action.id, { action: event.action, settings: controlSettings(event.payload.settings) });
		await this.refresh();
	}

	/**
	 * Remove the action that is no longer visible.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override onWillDisappear(event: WillDisappearEvent<ControlSettings>): void {
		this.keys.delete(event.action.id);
		this.rendering.forget(event.action.id);
	}

	/**
	 * Publish changed feedback for the currently visible device actions.
	 * @returns Completion of immediately admitted visual updates.
	 */
	private refresh(): Promise<void> {
		return Promise.all(
			[...this.keys].map(([context, key]) =>
				this.rendering.refresh(
					context,
					(values) => {
						const feedback = keyFeedback(this.client, context, key.settings);
						return {
							signature: JSON.stringify(feedback),
							updates: [
								...values.value("state", feedback.state, (state) => key.action.setState(state)),
								...values.value(`image:${feedback.state}`, feedback.image, (image) =>
									key.action.setImage(imageData(image), { state: feedback.state }),
								),
								...values.value(`title:${feedback.state}`, feedback.title, (title) =>
									key.action.setTitle(title, { state: feedback.state }),
								),
							],
						};
					},
					this.client.state?.session_id,
				),
			),
		).then(() => {});
	}
}
