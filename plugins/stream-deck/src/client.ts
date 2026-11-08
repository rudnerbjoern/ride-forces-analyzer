import streamDeck from "@elgato/streamdeck";
import { randomUUID } from "node:crypto";

import { decodeServerMessage } from "./decoder.js";
import { PROTOCOL_VERSION } from "./protocol.js";
import type { Action, Command, ConnectionState, StateEvent, Target } from "./protocol.js";
import { AnalyzerTransport, endpointPath } from "./transport.js";

const relativeActions = new Set<Action["name"]>([
	"library.move",
	"position.step",
	"selection.step",
	"view.zoom",
	"smoothing.step",
	"playback.speed.step",
	"marker.preview",
]);

export interface Transport {
	start(): void;
	stop(): void;
	send(message: string): boolean;
}
/**
 *
 */
export type TransportFactory = (message: (payload: string) => void, connected: (value: boolean) => void) => Transport;

/**
 * Compare opaque target identities without following focus changes.
 * @param first Previously addressed target, or null when no target is selected.
 * @param second Current target to compare against the previous identity.
 * @returns Whether both values identify the same window, recording and generation.
 */
export function sameTarget(first: Target | null, second: Target | null): boolean {
	return (
		first === second ||
		(first !== null &&
			second !== null &&
			first.window_id === second.window_id &&
			first.recording_id === second.recording_id &&
			first.generation === second.generation)
	);
}

/** Share one app connection across visible keys; retain only confirmed snapshots. */
export class ControlClient {
	/**
	 *
	 */
	private connection: ConnectionState = "disconnected";
	/**
	 *
	 */
	private current: StateEvent | undefined;
	/**
	 *
	 */
	private readonly failures = new Map<string, string>();
	/**
	 *
	 */
	private readonly listeners = new Set<(failedContext?: string) => void>();
	/** Last protocol rejection reason, deduplicated until recovery or reconnection. */
	private protocolIssue: "protocol.unsupported" | "server.message.invalid" | undefined;
	/**
	 *
	 */
	private readonly requests = new Map<
		string,
		{
			/**
			 *
			 */
			context: string;
			/** Validated command name, safe to include in failure diagnostics. */
			name: Action["name"];
			/**
			 *
			 */
			target: Target;
		}
	>();
	/**
	 *
	 */
	private readonly transport: Transport;

	/**
	 * Create one shared client with an injectable authenticated transport.
	 * @param factory Factory receiving incoming-message and connection-change callbacks.
	 */
	constructor(
		factory: TransportFactory = (message, connected) => new AnalyzerTransport(endpointPath(), message, connected),
	) {
		this.transport = factory(
			(payload) => this.receive(payload),
			(connected) => {
				this.current = undefined;
				this.requests.clear();
				this.failures.clear();
				this.protocolIssue = undefined;
				this.connection = connected ? "connecting" : "disconnected";
				this.notify();
			},
		);
	}

	/**
	 *
	 */
	public get state(): StateEvent | undefined {
		return this.current;
	}
	/**
	 *
	 */
	public get status(): ConnectionState {
		return this.connection;
	}
	/**
	 * Read the latest command failure for a device action.
	 * @param context Opaque SDK action context whose failure is requested.
	 * @returns Last failure code for this context, or undefined when none is retained.
	 */
	public error(context: string): string | undefined {
		return this.failures.get(context);
	}
	/**
	 * Check whether a device action has an outstanding command.
	 * @param context Opaque SDK action context to inspect.
	 * @returns Whether any unanswered request belongs to this context.
	 */
	public pending(context: string): boolean {
		return [...this.requests.values()].some((request) => request.context === context);
	}

	/**
	 * Send an available command against the currently confirmed target.
	 * @param context Opaque SDK action context used to track pending and failed requests.
	 * @param action Typed application command to send after availability checks.
	 * @returns Whether the transport accepted the command for sending.
	 */
	public send(context: string, action: Action): boolean {
		const state = this.current;
		if (
			this.connection !== "connected" ||
			!state?.target ||
			!state.availability.available ||
			!state.controls[action.name]?.available ||
			(this.pending(context) && !relativeActions.has(action.name))
		)
			return false;
		const command: Command = {
			version: PROTOCOL_VERSION,
			type: "command",
			id: randomUUID(),
			target: state.target,
			action,
		};
		this.requests.set(command.id, { context, name: action.name, target: command.target });
		this.failures.delete(context);
		if (!this.transport.send(JSON.stringify(command))) {
			this.requests.delete(command.id);
			this.notify();
			return false;
		}
		this.notify();
		return true;
	}
	/**
	 *
	 */
	public start(): void {
		this.transport.start();
	}
	/**
	 *
	 */
	public stop(): void {
		this.transport.stop();
	}

	/**
	 * Subscribe to connection, request and confirmed-state changes.
	 * @param listener Callback receiving the originating context only for a newly received command failure.
	 * @returns Function removing this listener from the client.
	 */
	public subscribe(listener: (failedContext?: string) => void): () => void {
		this.listeners.add(listener);
		return () => {
			this.listeners.delete(listener);
		};
	}

	/**
	 * Refresh subscribers and optionally identify one newly received command failure.
	 * @param failedContext Originating action context, absent for ordinary state changes.
	 */
	private notify(failedContext?: string): void {
		for (const listener of this.listeners) listener(failedContext);
	}

	/**
	 * Validate an incoming state or response before changing client feedback.
	 * @param payload Serialized server message received from the authenticated transport.
	 */
	private receive(payload: string): void {
		const message = decodeServerMessage(payload);
		let failedContext: string | undefined;
		if (!message) {
			if (this.protocolIssue !== "server.message.invalid") {
				streamDeck.logger.warn("Analyzer protocol rejected", {
					reason: "server.message.invalid",
					expectedVersion: PROTOCOL_VERSION,
				});
			}
			this.protocolIssue = "server.message.invalid";
			this.current = undefined;
			this.requests.clear();
			this.connection = "incompatible";
			this.notify();
			return;
		}
		if (message.type === "state") {
			this.protocolIssue = undefined;
			if (this.current?.session_id === message.session_id && message.sequence <= this.current.sequence) return;
			if (this.current?.session_id !== message.session_id || !sameTarget(this.current.target, message.target)) {
				this.requests.clear();
				this.failures.clear();
			}
			this.current = message;
			this.connection = "connected";
		} else {
			const request = message.id === null ? undefined : this.requests.get(message.id);
			if (!request || !sameTarget(request.target, message.target)) return;
			if (message.status !== "pending") this.requests.delete(message.id!);
			if (message.status === "error") {
				streamDeck.logger.warn("Analyzer command failed", {
					command: request.name,
					code: message.code,
					reason: message.reason,
				});
				this.failures.set(request.context, message.code);
				failedContext = request.context;
				if (message.code === "target.stale" || message.code === "protocol.unsupported") {
					this.current = undefined;
					this.requests.clear();
					if (message.code === "protocol.unsupported") {
						this.connection = "incompatible";
						this.protocolIssue = "protocol.unsupported";
					}
				}
			}
		}
		this.notify(failedContext);
	}
}
