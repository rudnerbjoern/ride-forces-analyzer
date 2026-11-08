import {
	action,
	type DialAction,
	type DialDownEvent,
	type DialRotateEvent,
	type DidReceiveSettingsEvent,
	SingletonAction,
	type TouchTapEvent,
	type WillAppearEvent,
	type WillDisappearEvent,
} from "@elgato/streamdeck";

import { type ControlClient, sameTarget } from "./client.js";
import { requestedAction } from "./controls.js";
import {
	dialBinding,
	dialSettings,
	type DialSettings,
	isPressOnly,
	type LibraryFilter,
	StepMode,
} from "./device-controls.js";
import { logFailure } from "./diagnostics.js";
import { FeedbackScheduler } from "./feedback-scheduler.js";
import { imageData } from "./feedback.js";
import { plusFeedback } from "./plus-feedback.js";

/** Shared Plus gesture handling; validation, bounds and analysis remain application-owned. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.dial" })
export class DialControlAction extends SingletonAction<DialSettings> {
	/**
	 *
	 */
	private readonly dials = new Map<
		string,
		{
			/**
			 *
			 */
			action: DialAction<DialSettings>;
			/**
			 *
			 */
			settings: DialSettings | undefined;
		}
	>();
	/**
	 *
	 */
	private previous: ControlClient["state"];
	/**
	 *
	 */
	private readonly proposals = new Map<string, Map<LibraryFilter, string | null>>();
	/**
	 *
	 */
	private readonly rendering = new FeedbackScheduler();

	/**
	 * Connect dial gestures and feedback to shared state and device-local step sizes.
	 * @param client Shared Analyzer client supplying confirmed state and command routing.
	 * @param mode Device-local sample-step selection shared across dial pages.
	 */
	constructor(
		private readonly client: ControlClient,
		private readonly mode: StepMode,
	) {
		super();
		this.previous = client.state;
		const refresh = (): void => {
			void this.refresh().catch((error) => logFailure("Dial feedback failed", error));
		};
		client.subscribe((failedContext) => {
			const dial = failedContext === undefined ? undefined : this.dials.get(failedContext);
			if (dial) void dial.action.showAlert().catch((error) => logFailure("Dial alert failed", error));
			this.synchronizeFilters();
			refresh();
		});
		mode.subscribe(refresh);
	}

	/**
	 * Apply the invoking dial's assigned press action.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onDialDown(event: DialDownEvent<DialSettings>): Promise<void> {
		if (event.payload.settings.control === "display") return;
		const settings = dialSettings(event.payload.settings);
		if (settings?.control === "filter") {
			if (!this.filterGesture(event.action, settings.filter!, "press")) await event.action.showAlert();
			return;
		}
		if (event.payload.settings.control === "selection") return;
		if (!this.invoke(event.action, event.payload.settings, "press", 1)) await event.action.showAlert();
	}

	/**
	 * Process each valid dial tick without inventing confirmed state.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onDialRotate(event: DialRotateEvent<DialSettings>): Promise<void> {
		if (isPressOnly(dialSettings(event.payload.settings)?.control) || event.payload.settings.control === "display")
			return;
		const ticks = event.payload.ticks;
		if (!Number.isSafeInteger(ticks) || ticks === 0) return;
		const settings = dialSettings(event.payload.settings);
		if (settings?.control === "filter") {
			if (!this.filterGesture(event.action, settings.filter!, "rotate", ticks)) await event.action.showAlert();
			return;
		}
		for (let index = 0; index < Math.abs(ticks); index++) {
			if (!this.invoke(event.action, event.payload.settings, "rotate", ticks < 0 ? -1 : 1)) {
				await event.action.showAlert();
				break;
			}
		}
	}

	/**
	 * Update the visible action after its saved settings change.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onDidReceiveSettings(event: DidReceiveSettingsEvent<DialSettings>): Promise<void> {
		if (!event.action.isDial()) return;
		this.resetFilters(event.action.device.id);
		this.dials.set(event.action.id, { action: event.action, settings: dialSettings(event.payload.settings) });
		await this.refresh();
	}

	/**
	 * Reset the invoking filter or discard only its marker preview.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onTouchTap(event: TouchTapEvent<DialSettings>): Promise<void> {
		if (event.payload.settings.control === "display") return;
		const settings = dialSettings(event.payload.settings);
		if (settings?.control === "filter") {
			if (!this.filterGesture(event.action, settings.filter!, "touch")) await event.action.showAlert();
			return;
		}
		// Marker touch discards only its associated preview; other fields have no touch command.
		if (event.payload.settings.control !== "marker") return;
		if (!this.invoke(event.action, event.payload.settings, "touch", 1)) await event.action.showAlert();
	}

	/**
	 * Register the visible action and refresh its confirmed feedback.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onWillAppear(event: WillAppearEvent<DialSettings>): Promise<void> {
		if (!event.action.isDial()) return;
		this.rendering.forget(event.action.id);
		const settings = dialSettings(event.payload.settings);
		await event.action.setTriggerDescription({
			rotate:
				isPressOnly(settings?.control) || settings?.control === "display"
					? ""
					: settings?.control === "library"
						? "Select one entry per notch"
						: "Adjust",
			push:
				settings?.control === "display"
					? ""
					: settings?.control === "filter"
						? "Filter"
						: settings?.control === "selection"
							? ""
							: settings?.control === "marker"
								? "Apply this preview"
								: settings?.control === "library"
									? "Open selection"
									: "Run assigned action",
			touch:
				settings?.control === "filter"
					? "Reset this filter to All"
					: settings?.control === "marker"
						? "Discard this preview"
						: "",
		});
		this.dials.set(event.action.id, { action: event.action, settings });
		await this.refresh();
	}

	/**
	 * Remove the action that is no longer visible.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override onWillDisappear(event: WillDisappearEvent<DialSettings>): void {
		const filter = this.dials.get(event.action.id)?.settings?.filter;
		if (filter) this.proposals.get(event.action.device.id)?.delete(filter);
		this.dials.delete(event.action.id);
		this.rendering.forget(event.action.id);
	}

	/**
	 * Discard this device's unconfirmed filter proposals.
	 * @param device SDK device identifier whose proposals should be removed.
	 */
	public resetFilters(device: string): void {
		this.proposals.delete(device);
		void this.refresh().catch((error) => logFailure("Filter feedback failed", error));
	}

	/**
	 * Update or send one device-local filter choice against current confirmed options.
	 * @param action_ Invoking dial whose visible binding and device are validated.
	 * @param filter Park or workflow-status filter addressed by this gesture.
	 * @param gesture Rotation proposes, press applies and touch requests All.
	 * @param ticks Signed number of option steps for a rotation event.
	 * @returns Whether the gesture was admitted or its filter command was sent.
	 */
	private filterGesture(
		action_: DialAction<DialSettings>,
		filter: LibraryFilter,
		gesture: "press" | "rotate" | "touch",
		ticks = 0,
	): boolean {
		// A late event from a vanished page must not operate on the current target.
		if (this.dials.get(action_.id)?.settings?.filter !== filter) return false;
		const device = action_.device.id;
		if (gesture === "touch") {
			this.proposals.get(device)?.delete(filter);
			void this.refresh().catch((error) => logFailure("Filter feedback failed", error));
		}
		const state = this.client.state;
		const choices = state?.library?.[`${filter}_filter`];
		if (
			this.client.status !== "connected" ||
			!state?.target ||
			!state.availability.available ||
			!state.controls["library.filter.set"]?.available ||
			!choices?.options.length
		)
			return false;
		const proposals = this.proposals.get(device) ?? new Map<LibraryFilter, string | null>();
		const value = proposals.has(filter) ? proposals.get(filter)! : choices.value;
		const index = choices.options.findIndex((option) => option.value === value);
		if (index < 0) return false;
		if (gesture === "rotate") {
			const next = choices.options[Math.max(0, Math.min(choices.options.length - 1, index + ticks))]!.value;
			if (next === choices.value) proposals.delete(filter);
			else proposals.set(filter, next);
			this.proposals.set(device, proposals);
			void this.refresh().catch((error) => logFailure("Filter feedback failed", error));
			return true;
		}
		const requested = gesture === "touch" ? null : value;
		if (!choices.options.some((option) => option.value === requested)) return false;
		return this.client.send(action_.id, { name: "library.filter.set", filter, value: requested });
	}

	/**
	 * Validate a dial binding and route its currently available command.
	 * @param action_ Invoking dial providing the device and request context.
	 * @param value Untrusted native settings to validate before mapping the gesture.
	 * @param gesture Rotation, press or touch input to map.
	 * @param direction Signed direction of this individual rotation tick.
	 * @returns Whether an available command was accepted by the shared client.
	 */
	private invoke(
		action_: DialAction<DialSettings>,
		value: DialSettings,
		gesture: "press" | "rotate" | "touch",
		direction: -1 | 1,
	): boolean {
		const settings = dialSettings(value);
		const binding = settings && dialBinding(settings, gesture, direction, this.mode.samples(action_.device.id));
		const requested = binding && requestedAction(binding, this.client.state);
		return requested !== undefined && this.client.send(action_.id, requested);
	}

	/**
	 * Publish changed feedback for the currently visible device actions.
	 * @returns Completion of immediately admitted visual updates.
	 */
	private refresh(): Promise<void> {
		return Promise.all(
			[...this.dials].map(([context, dial]) =>
				this.rendering.refresh(
					context,
					(values) => {
						const proposal = dial.settings?.filter
							? this.proposals.get(dial.action.device.id)?.get(dial.settings.filter)
							: undefined;
						const feedback = plusFeedback(
							this.client,
							context,
							dial.settings,
							this.mode.samples(dial.action.device.id),
							proposal,
						);
						const icon = imageData(feedback.icon);
						const { layout, detail, ...fields } = feedback;
						const updates = values.layout(layout, (value) => dial.action.setFeedbackLayout(value));
						const layoutChanged = updates.length > 0;
						updates.push(
							...values.value("configurationImage", icon, (value) => dial.action.setImage(value), layoutChanged),
							...values.fields(
								"feedback",
								{
									...fields,
									...(detail ? { detail } : {}),
									icon,
									band: imageData(feedback.band),
									statusIcon: imageData(feedback.statusIcon),
								},
								(changes) => dial.action.setFeedback(changes),
								layoutChanged,
							),
						);
						return { signature: JSON.stringify(feedback), updates };
					},
					this.client.state?.session_id,
				),
			),
		).then(() => {});
	}

	/**
	 *
	 */
	private synchronizeFilters(): void {
		const state = this.client.state;
		if (
			!state ||
			state.session_id !== this.previous?.session_id ||
			!sameTarget(state.target, this.previous?.target ?? null)
		) {
			this.proposals.clear();
		} else {
			for (const filter of ["park", "status"] as const) {
				if (
					JSON.stringify(state.library?.[`${filter}_filter`]) !==
					JSON.stringify(this.previous?.library?.[`${filter}_filter`])
				) {
					for (const proposals of this.proposals.values()) proposals.delete(filter);
				}
			}
		}
		this.previous = state;
	}
}
