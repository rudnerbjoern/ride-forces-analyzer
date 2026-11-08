import { logFailure } from "./diagnostics.js";

/** One visual frame whose SDK calls must fit in the action's transmission budget. */
export interface FeedbackFrame {
	/** Identity of the complete rendered feedback, for deduplication. */
	signature: string;
	/** SDK calls in wire order, including layout changes when needed. */
	updates: (() => Promise<void>)[];
}

/** Last successfully transmitted values, kept separately for each native API destination. */
class FeedbackValues {
	/** Complete values or merged layout fields confirmed as sent by the SDK. */
	private readonly sent = new Map<string, unknown>();

	/**
	 * Build one partial layout update containing only changed top-level fields.
	 * @param key Native feedback destination whose fields are compared.
	 * @param values Complete current layout values.
	 * @param send SDK call accepting a partial layout payload.
	 * @param force Whether a new layout requires every current field to be repainted.
	 * @returns One deferred update, or no calls when all fields are unchanged.
	 */
	public fields<T extends object>(
		key: string,
		values: T,
		send: (changes: Partial<T>) => Promise<void>,
		force = false,
	): (() => Promise<void>)[] {
		const previous = this.sent.get(key) as Partial<T> | undefined;
		const changes = Object.fromEntries(
			Object.entries(values).filter(
				([name, value]) => force || JSON.stringify(previous?.[name as keyof T]) !== JSON.stringify(value),
			),
		) as Partial<T>;
		if (Object.keys(changes).length === 0) return [];
		return [
			async () => {
				await send(changes);
				this.sent.set(key, force ? changes : { ...previous, ...changes });
			},
		];
	}

	/**
	 * Change a native layout and invalidate all content erased by that change.
	 * @param layout Native layout path whose successful change resets its fields.
	 * @param send SDK call selecting the native layout.
	 * @returns One deferred layout change, or no calls when the layout is unchanged.
	 */
	public layout(layout: string, send: (layout: string) => Promise<void>): (() => Promise<void>)[] {
		return this.value("layout", layout, async (value) => {
			await send(value);
			this.sent.clear();
		});
	}

	/**
	 * Build an SDK call only when its destination's value changed or needs repainting.
	 * @param key Native destination, including state-specific image/title targets.
	 * @param value Current value to compare against the last successful transmission.
	 * @param send SDK call sending this value.
	 * @param force Whether appearance or a layout change requires repainting.
	 * @returns One deferred update, or no calls when the value is unchanged.
	 */
	public value<T>(key: string, value: T, send: (value: T) => Promise<void>, force = false): (() => Promise<void>)[] {
		if (!force && this.sent.has(key) && JSON.stringify(this.sent.get(key)) === JSON.stringify(value)) return [];
		return [
			async () => {
				await send(value);
				this.sent.set(key, value);
			},
		];
	}
}

/** Pending latest-state renderer and the last successfully sent frame. */
interface Surface {
	/** Read current state when a budget slot becomes available. */
	create: (values: FeedbackValues) => FeedbackFrame;
	/** Last successfully sent fields for this visibility and connection generation. */
	values: FeedbackValues;
	/** Confirmed Analyzer session, absent when its target state is cleared. */
	session: string | undefined;
	/** Invalidate in-flight field-cache commits after a connection change. */
	generation: number;
	/** Whether an SDK batch is still completing. */
	running: boolean;
	/** Whether another refresh arrived during the current batch. */
	pending: boolean;
	/** Time of the last batch, preventing back-to-back visual refreshes. */
	lastSent: number;
	/** One wake-up for the latest pending frame. */
	timer?: ReturnType<typeof setTimeout>;
}

/** Coalesce latest-state frames with at most ten visual SDK calls per action per rolling second. */
export class FeedbackScheduler {
	/** Actual call timestamps, retained across disappearance/reappearance within the same second. */
	private readonly calls = new Map<string, number[]>();
	/** Currently visible actions and their pending renderers. */
	private readonly surfaces = new Map<string, Surface>();

	/**
	 * Cancel pending visuals for an action that is no longer visible.
	 * @param context SDK action identity removed by its disappearance event.
	 */
	public forget(context: string): void {
		const surface = this.surfaces.get(context);
		if (surface?.timer) clearTimeout(surface.timer);
		this.surfaces.delete(context);
	}

	/**
	 * Request current feedback, replacing any frame waiting for a transmission slot.
	 * @param context SDK action identity whose visual calls share one budget.
	 * @param create Renderer reading the latest confirmed state when it runs.
	 * @param session Confirmed Analyzer session; absence invalidates connected feedback.
	 * @returns Completion of immediately admitted calls; delayed frames use one timer.
	 */
	public refresh(context: string, create: (values: FeedbackValues) => FeedbackFrame, session?: string): Promise<void> {
		for (const [id, history] of this.calls) {
			if (!this.surfaces.has(id) && history.at(-1)! <= Date.now() - 1000) this.calls.delete(id);
		}
		let surface = this.surfaces.get(context);
		if (!surface) {
			surface = {
				create,
				values: new FeedbackValues(),
				session,
				generation: 0,
				running: false,
				pending: false,
				lastSent: -Infinity,
			};
			this.surfaces.set(context, surface);
		}
		if (surface.session !== session) {
			surface.session = session;
			surface.values = new FeedbackValues();
			surface.generation++;
		}
		surface.create = create;
		surface.pending = true;
		return this.flush(context, surface);
	}

	/**
	 * Send a changed frame when both its complete call budget and refresh interval permit it.
	 * @param context SDK action identity whose calls are counted.
	 * @param surface Pending renderer, discarded if the action has since disappeared.
	 * @returns Completion of an admitted batch, or immediate completion after scheduling.
	 */
	private async flush(context: string, surface: Surface): Promise<void> {
		if (this.surfaces.get(context) !== surface || surface.running || surface.timer) return;
		const generation = surface.generation;
		const frame = surface.create(surface.values);
		surface.pending = false;
		if (frame.updates.length === 0) return;
		const now = Date.now();
		const history = (this.calls.get(context) ?? []).filter((time) => time > now - 1000);
		this.calls.set(context, history);
		const excess = history.length + frame.updates.length - 10;
		const wait = Math.max(surface.lastSent + 100 - now, excess > 0 ? history[excess - 1]! + 1000 - now : 0);
		if (wait > 0) {
			surface.timer = setTimeout(() => {
				delete surface.timer;
				void this.flush(context, surface).catch((error) => logFailure("Stream Deck feedback failed", error));
			}, wait);
			return;
		}
		surface.running = true;
		surface.lastSent = now;
		try {
			for (const update of frame.updates) {
				if (this.surfaces.get(context) !== surface) return;
				if (surface.generation !== generation || surface.create(surface.values).signature !== frame.signature) {
					surface.pending = true;
					return;
				}
				history.push(Date.now());
				await update();
			}
			if (surface.generation !== generation) surface.pending = true;
		} finally {
			surface.running = false;
			if (surface.pending) await this.flush(context, surface);
		}
	}
}
