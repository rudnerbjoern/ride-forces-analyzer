import streamDeck from "@elgato/streamdeck";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";

/** Safe connection outcomes; never include discovery contents or server-provided text. */
type ConnectionReason =
	| "authentication.closed"
	| "authentication.invalid"
	| "authentication.rejected"
	| "authentication.send.failed"
	| "authentication.timeout"
	| "connection.closed"
	| "connection.established"
	| "connection.failed"
	| "discovery.invalid"
	| "discovery.missing"
	| "discovery.unreadable"
	| "message.send.failed"
	| "message.text.required"
	| "transport.stopped";

interface Endpoint {
	/**
	 *
	 */
	version: 1;
	/**
	 *
	 */
	port: number;
	/**
	 *
	 */
	token: string;
}

/**
 * Locate discovery using Analyzer's native application-data conventions.
 * @param platform Operating-system identifier selecting Windows or macOS paths.
 * @param environment Environment variables supplying the Windows local-data directory.
 * @param home Home-directory fallback when no local-data variable is present.
 * @returns Native path of the shared discovery file.
 */
export function endpointPath(
	platform: string = process.platform,
	environment: NodeJS.ProcessEnv = process.env,
	home: string = homedir(),
): string {
	if (platform === "win32") {
		return path.win32.join(
			environment.LOCALAPPDATA || path.win32.join(home, "AppData", "Local"),
			"Ride Forces Analyzer",
			"stream-deck.json",
		);
	}
	if (platform === "darwin") {
		return path.posix.join(home, "Library", "Application Support", "Ride Forces Analyzer", "stream-deck.json");
	}
	throw new Error("Stream Deck discovery requires Windows or macOS");
}

/**
 * Read and validate the local transport discovery file.
 * @param filename Discovery file containing the handshake version, port and token.
 * @returns Validated loopback port and authentication token.
 */
async function readEndpoint(filename: string): Promise<Endpoint> {
	const value: unknown = JSON.parse(await readFile(filename, "utf8"));
	if (
		typeof value !== "object" ||
		value === null ||
		!("version" in value) ||
		value.version !== 1 ||
		!("port" in value) ||
		typeof value.port !== "number" ||
		!Number.isInteger(value.port) ||
		value.port < 1 ||
		value.port > 65535 ||
		!("token" in value) ||
		typeof value.token !== "string" ||
		!/^[a-f0-9]{64}$/.test(value.token)
	) {
		throw new Error("Invalid Stream Deck transport discovery");
	}
	return { version: 1, port: value.port, token: value.token };
}

/** Authenticated text transport; reconnects rediscover the endpoint and never replay commands. */
export class AnalyzerTransport {
	/**
	 *
	 */
	private authenticated = false;
	/**
	 *
	 */
	private readonly endpointFile: string;
	/**
	 *
	 */
	private generation = 0;
	/**
	 *
	 */
	private readonly onConnection: (connected: boolean) => void;
	/**
	 *
	 */
	private readonly onMessage: (message: string) => void;
	/** Last connection outcome, retained across identical offline retries. */
	private reason: ConnectionReason | undefined;
	/**
	 *
	 */
	private retry: NodeJS.Timeout | undefined;
	/**
	 *
	 */
	private socket: WebSocket | undefined;
	/**
	 *
	 */
	private stopped = true;

	/**
	 * Configure an authenticated reconnecting transport without starting it.
	 * @param endpointFile Discovery path to reread before each connection attempt.
	 * @param onMessage Callback receiving authenticated application message text.
	 * @param onConnection Callback receiving changes to authenticated connection availability.
	 */
	constructor(
		endpointFile: string,
		onMessage: (message: string) => void,
		onConnection: (connected: boolean) => void = () => {},
	) {
		this.endpointFile = endpointFile;
		this.onMessage = onMessage;
		this.onConnection = onConnection;
	}

	/**
	 *
	 */
	public get connected(): boolean {
		return this.authenticated;
	}

	/**
	 * Send a message only while the current socket is authenticated and open.
	 * @param message Serialized application command to send without queuing.
	 * @returns Whether the message was sent on the current authenticated socket.
	 */
	public send(message: string): boolean {
		if (!this.authenticated || this.socket?.readyState !== WebSocket.OPEN) return false;
		try {
			this.socket.send(message);
			return true;
		} catch {
			this.setReason("message.send.failed");
			const socket = this.socket;
			this.socket = undefined;
			socket.close();
			this.setConnected(false);
			this.scheduleRetry();
			return false;
		}
	}

	/**
	 *
	 */
	public start(): void {
		if (!this.stopped) return;
		this.stopped = false;
		this.generation++;
		void this.connect();
	}

	/**
	 *
	 */
	public stop(): void {
		this.stopped = true;
		this.generation++;
		clearTimeout(this.retry);
		this.retry = undefined;
		const socket = this.socket;
		this.socket = undefined;
		socket?.close();
		this.setConnected(false);
		this.setReason("transport.stopped");
	}

	/**
	 *
	 */
	private async connect(): Promise<void> {
		const generation = this.generation;
		let endpoint: Endpoint;
		try {
			endpoint = await readEndpoint(this.endpointFile);
		} catch (error) {
			if (!this.stopped && generation === this.generation) {
				const code = typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
				this.setReason(code === "ENOENT" ? "discovery.missing" : code ? "discovery.unreadable" : "discovery.invalid");
				this.scheduleRetry();
			}
			return;
		}
		if (this.stopped || generation !== this.generation) return;
		let socket: WebSocket;
		try {
			socket = new WebSocket(`ws://127.0.0.1:${endpoint.port}`);
		} catch {
			this.setReason("connection.failed");
			this.scheduleRetry();
			return;
		}
		this.socket = socket;
		let failed = false;
		let opened = false;
		const fail = (reason: ConnectionReason): void => {
			if (this.socket !== socket || failed) return;
			failed = true;
			clearTimeout(deadline);
			this.setReason(reason);
			socket.close();
		};
		const deadline = setTimeout(() => fail("authentication.timeout"), 5000);
		deadline.unref?.();
		socket.addEventListener("open", () => {
			if (this.socket !== socket) return;
			opened = true;
			try {
				socket.send(JSON.stringify({ version: 1, token: endpoint.token }));
			} catch {
				fail("authentication.send.failed");
			}
		});
		socket.addEventListener("message", (event) => {
			if (this.socket !== socket) return;
			if (typeof event.data !== "string") {
				fail("message.text.required");
				return;
			}
			if (!this.authenticated) {
				let ready: unknown;
				try {
					ready = JSON.parse(event.data);
				} catch {
					fail("authentication.invalid");
					return;
				}
				if (
					typeof ready !== "object" ||
					ready === null ||
					!("transport" in ready) ||
					ready.transport !== "ready" ||
					!("version" in ready) ||
					ready.version !== 1
				) {
					fail("authentication.rejected");
					return;
				}
				clearTimeout(deadline);
				this.setReason("connection.established");
				this.setConnected(true);
			} else {
				this.onMessage(event.data);
			}
		});
		socket.addEventListener("error", () => fail("connection.failed"));
		socket.addEventListener("close", (event) => {
			clearTimeout(deadline);
			if (this.socket !== socket) return;
			if (!failed)
				this.setReason(
					this.authenticated
						? "connection.closed"
						: !opened
							? "connection.failed"
							: event.code === 1008
								? "authentication.rejected"
								: "authentication.closed",
				);
			this.socket = undefined;
			this.setConnected(false);
			this.scheduleRetry();
		});
	}

	/**
	 *
	 */
	private scheduleRetry(): void {
		if (this.stopped || this.retry) return;
		this.retry = setTimeout(() => {
			this.retry = undefined;
			void this.connect();
		}, 1000);
		this.retry.unref?.();
	}

	/**
	 * Publish an authenticated-connection change only when its value differs.
	 * @param connected New authenticated availability of the current socket.
	 */
	private setConnected(connected: boolean): void {
		if (this.authenticated !== connected) {
			this.authenticated = connected;
			this.onConnection(connected);
		}
	}

	/**
	 * Log only transitions between fixed connection outcomes, without payload data.
	 * @param reason Safe discovery, authentication or connection classification.
	 */
	private setReason(reason: ConnectionReason): void {
		if (reason === this.reason) return;
		this.reason = reason;
		const level = ["discovery.missing", "connection.closed", "connection.established", "transport.stopped"].includes(
			reason,
		)
			? "info"
			: "warn";
		streamDeck.logger[level]("Analyzer connection", { reason });
	}
}
