import {
	action,
	type DidReceiveSettingsEvent,
	type NeoInfobarAction,
	SingletonAction,
	type WillAppearEvent,
	type WillDisappearEvent,
} from "@elgato/streamdeck";

import type { ControlClient } from "./client.js";
import type { InfoSettings } from "./device-controls.js";
import { infoFeedback } from "./device-feedback.js";
import { logFailure } from "./diagnostics.js";
import { FeedbackScheduler } from "./feedback-scheduler.js";
import { imageData } from "./feedback.js";

/** Contextual Neo display; intentionally has no input handlers or command path. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.infobar" })
export class InfoBarAction extends SingletonAction<InfoSettings> {
	/**
	 *
	 */
	private readonly bars = new Map<
		string,
		{
			/**
			 *
			 */
			action: NeoInfobarAction<InfoSettings>;
			/**
			 *
			 */
			settings: InfoSettings;
		}
	>();
	/**
	 *
	 */
	private readonly rendering = new FeedbackScheduler();
	/**
	 * Subscribe the display-only Neo InfoBar to confirmed Analyzer state.
	 * @param client Shared client publishing connection and application state.
	 */
	constructor(private readonly client: ControlClient) {
		super();
		client.subscribe(() => {
			void this.refresh().catch((error) => logFailure("InfoBar feedback failed", error));
		});
	}
	/**
	 * Update the visible action after its saved settings change.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onDidReceiveSettings(event: DidReceiveSettingsEvent<InfoSettings>): Promise<void> {
		if (!event.action.isNeoInfobar()) return;
		this.bars.set(event.action.id, {
			...this.bars.get(event.action.id),
			action: event.action,
			settings: event.payload.settings,
		});
		await this.refresh();
	}
	/**
	 * Register the visible action and refresh its confirmed feedback.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onWillAppear(event: WillAppearEvent<InfoSettings>): Promise<void> {
		if (!event.action.isNeoInfobar()) return;
		this.rendering.forget(event.action.id);
		this.bars.set(event.action.id, { action: event.action, settings: event.payload.settings });
		await this.refresh();
	}
	/**
	 * Remove the action that is no longer visible.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override onWillDisappear(event: WillDisappearEvent<InfoSettings>): void {
		this.bars.delete(event.action.id);
		this.rendering.forget(event.action.id);
	}
	/**
	 * Publish changed feedback for the currently visible device actions.
	 * @returns Completion of immediately admitted visual updates.
	 */
	private refresh(): Promise<void> {
		return Promise.all(
			[...this.bars].map(([context, bar]) =>
				this.rendering.refresh(
					context,
					(values) => {
						const feedback = infoFeedback(this.client, bar.settings);
						const updates = values.layout("layouts/neo.json", (layout) => bar.action.setFeedbackLayout(layout));
						updates.push(
							...values.fields(
								"feedback",
								{ ...feedback, icon: imageData(feedback.icon) },
								(changes) => bar.action.setFeedback(changes),
								updates.length > 0,
							),
						);
						return { signature: JSON.stringify(feedback), updates };
					},
					this.client.state?.session_id,
				),
			),
		).then(() => {});
	}
}
