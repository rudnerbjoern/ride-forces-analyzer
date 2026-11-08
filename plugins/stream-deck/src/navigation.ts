import streamDeck, {
	action,
	type KeyAction,
	type KeyDownEvent,
	SingletonAction,
	type WillAppearEvent,
	type WillDisappearEvent,
} from "@elgato/streamdeck";

import type { ControlClient } from "./client.js";
import { logFailure } from "./diagnostics.js";
import { FeedbackScheduler } from "./feedback-scheduler.js";
import { type IconStatus, imageData, keyImage, keyTitle } from "./feedback.js";

export const PLUS_PAGES = [
	{ id: "library", name: "Library", group: "library" },
	{ id: "playback", name: "Playback / Navigate", group: "playback" },
	{ id: "selection", name: "Playback / Selection", group: "playback" },
	{ id: "curves", name: "Curves", group: "curves" },
	{ id: "markers", name: "Markers / Markers", group: "markers" },
	{ id: "marker-view", name: "Markers / View", group: "markers" },
] as const;
/**
 *
 */
export type PlusPage = 0 | 1 | 2 | 3 | 4 | 5;
/**
 *
 */
type Group = (typeof PLUS_PAGES)[number]["group"];
/**
 *
 */
export type NavigationSettings = {
	/**
	 *
	 */
	page: PlusPage;
	/**
	 *
	 */
	target: Group | 1 | 2 | 4 | 5;
};

/**
 * Admit only the fixed Plus menu and the visible group's subgroup keys.
 * @param value Untrusted page index and navigation target from native settings.
 * @returns Validated page binding, or undefined for invalid or unrelated targets.
 */
export function navigationSettings(value: Record<string, unknown>): NavigationSettings | undefined {
	if (typeof value.page !== "number" || !Number.isInteger(value.page) || value.page < 0 || value.page > 5)
		return undefined;
	const group = PLUS_PAGES[value.page]?.group;
	if (
		!["library", "playback", "curves", "markers"].includes(value.target as string) &&
		!(group === "playback" && (value.target === 1 || value.target === 2)) &&
		!(group === "markers" && (value.target === 4 || value.target === 5))
	)
		return undefined;
	return { page: value.page as PlusPage, target: value.target as NavigationSettings["target"] };
}

/**
 * Render local page selection and confirmed application menu captions.
 * @param settings Fixed menu or subgroup binding being rendered.
 * @param confirmed Page index confirmed by native appearance events, if known.
 * @param client Optional confirmed application state and connection status.
 * @returns Menu title, artwork and confirmed local selection flag.
 */
export function navigationFeedback(
	settings: NavigationSettings,
	confirmed: PlusPage | undefined,
	client?: Pick<ControlClient, "state" | "status">,
): {
	/**
	 *
	 */
	title: string;
	/**
	 *
	 */
	image: string;
	/**
	 *
	 */
	selected: boolean;
} {
	const target = settings.target;
	let title =
		typeof target === "string"
			? { library: "Library", playback: "Playback", curves: "Curves", markers: "Markers" }[target]
			: { 1: "Navigate", 2: "Selection", 4: "Markers", 5: "View" }[target];
	const symbol =
		target === "curves"
			? "combined"
			: target === 1
				? "position"
				: target === 2
					? "selection"
					: target === 4
						? "markers"
						: target === 5
							? "view"
							: target;
	const selected =
		confirmed !== undefined &&
		(typeof target === "string" ? PLUS_PAGES[confirmed].group === target : confirmed === target);
	let status: IconStatus | undefined;
	if (typeof target === "string") {
		let caption: string;
		const state = client?.state;
		if (client?.status !== "connected" || !state) {
			caption =
				client?.status === "connecting" ? "Connecting…" : client?.status === "incompatible" ? "Version err" : "Offline";
			status = "disconnected";
		} else if (target === "library") {
			const library = state.library;
			caption = library?.selected
				? `${library.selected.index + 1}/${library.count}`
				: library
					? library.count === 0
						? "Empty"
						: `—/${library.count}`
					: "No Explorer";
		} else if (target === "playback") {
			caption = state.playback ? (state.playback.playing ? "Playing" : "Paused") : "No data";
		} else if (target === "curves") {
			const mode = state.curves.find((curve) => curve.curve === "calibrated");
			caption = mode ? (mode.active ? "Calibrated" : "Raw") : "No data";
		} else {
			const previews = state.markers.filter((marker) => marker.preview !== null).length;
			status = state.markers.some((marker) => marker.status === "failed")
				? "failed"
				: state.markers.some((marker) => marker.status === "pending")
					? "pending"
					: previews > 0
						? "preview"
						: undefined;
			caption =
				status === "failed"
					? "Failed"
					: status === "pending"
						? "Pending"
						: previews > 0
							? `${previews} ${previews === 1 ? "preview" : "previews"}`
							: state.markers.length === 0
								? "No data"
								: "No preview";
		}
		title = keyTitle(`${title}\n${caption}`);
	}
	const image = keyImage(symbol, status).replace(
		"</svg>",
		selected
			? '<rect x="2" y="2" width="140" height="140" rx="16" fill="none" stroke="#64d6ff" stroke-width="3"/>' +
					'<path d="M16 136h112" stroke="#64d6ff" stroke-width="3"/></svg>'
			: "</svg>",
	);
	return { title, image, selected };
}

/** Switch only the invoking Plus; remember subgroups from confirmed appearances. */
@action({ UUID: "io.github.rudnerbjoern.ride-forces-analyzer.plus-navigation" })
export class PlusNavigationAction extends SingletonAction<NavigationSettings> {
	/**
	 *
	 */
	private readonly devices = new Map<
		string,
		{
			/**
			 *
			 */
			page: PlusPage | undefined;
			/**
			 *
			 */
			playback: 1 | 2;
			/**
			 *
			 */
			markers: 4 | 5;
		}
	>();
	/**
	 *
	 */
	private readonly keys = new Map<
		string,
		{
			/**
			 *
			 */
			action: KeyAction<NavigationSettings>;
			/**
			 *
			 */
			settings: NavigationSettings;
		}
	>();
	/**
	 *
	 */
	private readonly rendering = new FeedbackScheduler();
	/**
	 *
	 */
	private readonly sending = new Set<string>();

	/**
	 * Connect native Plus page navigation to confirmed application feedback.
	 * @param client Shared client supplying confirmed captions and availability.
	 * @param switchProfile SDK function requesting a page of the invoking device's bundled profile.
	 */
	constructor(
		private readonly client: ControlClient,
		private readonly switchProfile = streamDeck.profiles.switchToProfile,
	) {
		super();
		client.subscribe(() => {
			void this.refresh().catch((error) => logFailure("Plus menu feedback failed", error));
		});
	}

	/**
	 * Handle a key press from the invoking device.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onKeyDown(event: KeyDownEvent<NavigationSettings>): Promise<void> {
		const settings = navigationSettings(event.payload.settings);
		if (event.action.device.type !== 7 || !settings) {
			await event.action.showAlert();
			return;
		}
		const id = event.action.device.id;
		const device = this.device(id);
		const target = settings.target;
		const page =
			target === "library"
				? 0
				: target === "curves"
					? 3
					: target === "playback"
						? device.playback
						: target === "markers"
							? device.markers
							: target;
		if (page === device.page || this.sending.has(id)) return;
		this.sending.add(id);
		try {
			await this.switchProfile(id, "profiles/plus", page);
			streamDeck.logger.info("Plus page request sent", { device: id, page });
		} catch (error) {
			logFailure("Plus page request failed", error, "warn");
			await event.action.showAlert();
		} finally {
			this.sending.delete(id);
		}
	}

	/**
	 * Register the visible action and refresh its confirmed feedback.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override async onWillAppear(event: WillAppearEvent<NavigationSettings>): Promise<void> {
		const settings = navigationSettings(event.payload.settings);
		if (event.action.device.type !== 7 || !event.action.isKey() || !settings) return;
		this.rendering.forget(event.action.id);
		const device = this.device(event.action.device.id);
		if (device.page !== settings.page)
			streamDeck.logger.info("Plus page appeared", { device: event.action.device.id, page: settings.page });
		device.page = settings.page;
		if (settings.page === 1 || settings.page === 2) device.playback = settings.page;
		if (settings.page === 4 || settings.page === 5) device.markers = settings.page;
		this.keys.set(event.action.id, { action: event.action, settings });
		await this.refresh();
	}

	/**
	 * Remove the action that is no longer visible.
	 * @param event SDK event identifying the action, device and current settings.
	 */
	public override onWillDisappear(event: WillDisappearEvent<NavigationSettings>): void {
		this.keys.delete(event.action.id);
		this.rendering.forget(event.action.id);
		if (![...this.keys.values()].some((key) => key.action.device.id === event.action.device.id)) {
			this.device(event.action.device.id).page = undefined;
		}
	}

	/**
	 * Get or initialize session navigation state for one Plus.
	 * @param id SDK device identifier whose remembered subgroups are requested.
	 * @returns Mutable page and subgroup state belonging only to this device.
	 */
	private device(id: string) {
		let state = this.devices.get(id);
		if (!state) {
			state = { page: undefined, playback: 1, markers: 4 };
			this.devices.set(id, state);
		}
		return state;
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
						const feedback = navigationFeedback(key.settings, this.device(key.action.device.id).page, this.client);
						const state = feedback.selected ? 1 : 0;
						return {
							signature: JSON.stringify(feedback),
							updates: [
								...values.value("state", state, (value) => key.action.setState(value)),
								...values.value(`image:${state}`, feedback.image, (image) =>
									key.action.setImage(imageData(image), { state }),
								),
								...values.value(`title:${state}`, feedback.title, (title) => key.action.setTitle(title, { state })),
							],
						};
					},
					this.client.state?.session_id,
				),
			),
		).then(() => {});
	}
}
