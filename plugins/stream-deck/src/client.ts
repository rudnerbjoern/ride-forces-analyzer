import { randomUUID } from "node:crypto";

import { decodeServerMessage } from "./decoder.js";
import type { Action, Command, ConnectionState, StateEvent, Target } from "./protocol.js";
import { AnalyzerTransport, endpointPath } from "./transport.js";

const relativeActions = new Set<Action["name"]>(["library.move", "position.step", "view.zoom",
    "smoothing.step", "playback.speed.step", "marker.preview"]);

export interface Transport {
    start(): void;
    stop(): void;
    send(message: string): boolean;
}
export type TransportFactory = (message: (payload: string) => void, connected: (value: boolean) => void) => Transport;

/** Compare opaque contexts rather than silently following focus changes. */
export function sameTarget(first: Target | null, second: Target | null): boolean {
    return first === second || first !== null && second !== null && first.window_id === second.window_id
        && first.recording_id === second.recording_id && first.generation === second.generation;
}

/** Share one app connection across visible keys; retain only confirmed snapshots. */
export class ControlClient {
    private readonly transport: Transport;
    private readonly listeners = new Set<() => void>();
    private readonly requests = new Map<string, { context: string; target: Target }>();
    private readonly failures = new Map<string, string>();
    private current: StateEvent | undefined;
    private connection: ConnectionState = "disconnected";

    constructor(factory: TransportFactory = (message, connected) =>
        new AnalyzerTransport(endpointPath(), message, connected)) {
        this.transport = factory(payload => this.receive(payload), connected => {
            this.current = undefined;
            this.requests.clear();
            this.failures.clear();
            this.connection = connected ? "connecting" : "disconnected";
            this.notify();
        });
    }

    get state(): StateEvent | undefined { return this.current; }
    get status(): ConnectionState { return this.connection; }
    start(): void { this.transport.start(); }
    stop(): void { this.transport.stop(); }

    subscribe(listener: () => void): () => void {
        this.listeners.add(listener);
        return () => { this.listeners.delete(listener); };
    }
    pending(context: string): boolean {
        return [...this.requests.values()].some(request => request.context === context);
    }
    error(context: string): string | undefined { return this.failures.get(context); }

    send(context: string, action: Action): boolean {
        const state = this.current;
        if (this.connection !== "connected" || !state?.target || !state.availability.available
            || !state.controls[action.name]?.available
            || this.pending(context) && !relativeActions.has(action.name)) return false;
        const command: Command = { version: 1, type: "command", id: randomUUID(), target: state.target, action };
        this.requests.set(command.id, { context, target: command.target });
        this.failures.delete(context);
        if (!this.transport.send(JSON.stringify(command))) {
            this.requests.delete(command.id);
            this.notify();
            return false;
        }
        this.notify();
        return true;
    }

    private notify(): void { for (const listener of this.listeners) listener(); }

    private receive(payload: string): void {
        const message = decodeServerMessage(payload);
        if (!message) {
            this.current = undefined;
            this.requests.clear();
            this.connection = "incompatible";
            this.notify();
            return;
        }
        if (message.type === "state") {
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
                this.failures.set(request.context, message.code);
                if (message.code === "stale_target" || message.code === "unsupported_protocol") {
                    this.current = undefined;
                    this.requests.clear();
                    if (message.code === "unsupported_protocol") this.connection = "incompatible";
                }
            }
        }
        this.notify();
    }
}
