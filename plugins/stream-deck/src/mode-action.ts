import {
	action,
	type KeyDownEvent,
	SingletonAction,
	type WillAppearEvent,
	type WillDisappearEvent,
} from "@elgato/streamdeck";

import { StepMode } from "./device-controls.js";
import { logFailure } from "./diagnostics.js";
import { FeedbackScheduler } from "./feedback-scheduler.js";
import { imageData, keyImage } from "./feedback.js";
import { displayText } from "./localization.js";

/** The 1/10/20-sample cycle is local to each Plus; marker presses remain Apply. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.step-mode" })
export class StepModeAction extends SingletonAction {
	/**
	 *
	 */
	private readonly keys = new Map<string, KeyDownEvent["action"]>();
	/**
	 *
	 */
	private readonly rendering = new FeedbackScheduler();
	/**
	 * Refresh step-size keys when the device-local sample increment changes.
	 * @param mode Device-local sample-step selection to display and cycle.
	 */
	constructor(private readonly mode: StepMode) {
		super();
		mode.subscribe(() => {
			void this.refresh().catch((error) => logFailure("Step mode feedback failed", error));
		});
	}
	/**
	 * Handle a key press from the invoking device.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onKeyDown(event: KeyDownEvent): Promise<void> {
		this.mode.toggle(event.action.device.id);
		await this.refresh();
	}
	/**
	 * Register the visible action and refresh its confirmed feedback.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onWillAppear(event: WillAppearEvent): Promise<void> {
		if (!event.action.isKey()) return;
		this.rendering.forget(event.action.id);
		this.keys.set(event.action.id, event.action);
		await this.refresh();
	}
	/**
	 * Remove the action that is no longer visible.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override onWillDisappear(event: WillDisappearEvent): void {
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
				this.rendering.refresh(context, (values) => {
					const samples = this.mode.samples(key.device.id);
					const state = samples === 1 ? 0 : samples === 10 ? 1 : 2;
					const label = samples === 1 ? "Fine" : samples === 10 ? "Medium" : "Coarse";
					const icon = samples === 1 ? "fine" : samples === 10 ? "medium" : "coarse";
					const image = keyImage(icon, undefined);
					const title = displayText(`${label}\n${samples} ${samples === 1 ? "sample" : "samples"}`);
					return {
						signature: JSON.stringify({ state, image, title }),
						updates: [
							...values.value("state", state, (value) => key.setState(value)),
							...values.value(`image:${state}`, image, (value) => key.setImage(imageData(value), { state })),
							...values.value(`title:${state}`, title, (value) => key.setTitle(value, { state })),
						],
					};
				}),
			),
		).then(() => {});
	}
}
