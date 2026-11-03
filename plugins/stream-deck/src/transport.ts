import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";

interface Endpoint {
    version: 1;
    port: number;
    token: string;
}

/** Locate discovery using the Analyzer's existing native data-directory convention. */
export function endpointPath(
    platform: string = process.platform,
    environment: NodeJS.ProcessEnv = process.env,
    home: string = homedir(),
): string {
    if (platform === "win32") {
        return path.win32.join(environment.LOCALAPPDATA || path.win32.join(home, "AppData", "Local"),
            "Ride Forces Analyzer", "stream-deck.json");
    }
    if (platform === "darwin") {
        return path.posix.join(home, "Library", "Application Support", "Ride Forces Analyzer", "stream-deck.json");
    }
    throw new Error("Stream Deck discovery requires Windows or macOS");
}

async function readEndpoint(filename: string): Promise<Endpoint> {
    const value: unknown = JSON.parse(await readFile(filename, "utf8"));
    if (typeof value !== "object" || value === null || !("version" in value) || value.version !== 1
        || !("port" in value) || typeof value.port !== "number" || !Number.isInteger(value.port)
        || value.port < 1 || value.port > 65535
        || !("token" in value) || typeof value.token !== "string" || !/^[a-f0-9]{64}$/.test(value.token)) {
        throw new Error("Invalid Stream Deck transport discovery");
    }
    return { version: 1, port: value.port, token: value.token };
}

/** Authenticated text transport; reconnects rediscover the endpoint and never replay commands. */
export class AnalyzerTransport {
    private readonly endpointFile: string;
    private readonly onMessage: (message: string) => void;
    private readonly onConnection: (connected: boolean) => void;
    private socket: WebSocket | undefined;
    private retry: NodeJS.Timeout | undefined;
    private stopped = true;
    private generation = 0;
    private authenticated = false;

    constructor(
        endpointFile: string,
        onMessage: (message: string) => void,
        onConnection: (connected: boolean) => void = () => {},
    ) {
        this.endpointFile = endpointFile;
        this.onMessage = onMessage;
        this.onConnection = onConnection;
    }

    get connected(): boolean {
        return this.authenticated;
    }

    start(): void {
        if (!this.stopped) return;
        this.stopped = false;
        this.generation++;
        void this.connect();
    }

    stop(): void {
        this.stopped = true;
        this.generation++;
        clearTimeout(this.retry);
        this.retry = undefined;
        const socket = this.socket;
        this.socket = undefined;
        socket?.close();
        this.setConnected(false);
    }

    /** Return false while disconnected; callers must obtain fresh state before retrying a command. */
    send(message: string): boolean {
        if (!this.authenticated || this.socket?.readyState !== WebSocket.OPEN) return false;
        this.socket.send(message);
        return true;
    }

    private setConnected(connected: boolean): void {
        if (this.authenticated !== connected) {
            this.authenticated = connected;
            this.onConnection(connected);
        }
    }

    private scheduleRetry(): void {
        if (this.stopped || this.retry) return;
        this.retry = setTimeout(() => {
            this.retry = undefined;
            void this.connect();
        }, 1000);
        this.retry.unref();
    }

    private async connect(): Promise<void> {
        const generation = this.generation;
        let endpoint: Endpoint;
        try {
            endpoint = await readEndpoint(this.endpointFile);
        } catch {
            if (!this.stopped && generation === this.generation) this.scheduleRetry();
            return;
        }
        if (this.stopped || generation !== this.generation) return;
        const socket = new WebSocket(`ws://127.0.0.1:${endpoint.port}`);
        this.socket = socket;
        const deadline = setTimeout(() => socket.close(), 5000);
        deadline.unref();
        socket.addEventListener("open", () => {
            if (this.socket === socket) socket.send(JSON.stringify({ version: 1, token: endpoint.token }));
        });
        socket.addEventListener("message", (event) => {
            if (this.socket !== socket) return;
            if (typeof event.data !== "string") {
                socket.close();
                return;
            }
            if (!this.authenticated) {
                let ready: unknown;
                try {
                    ready = JSON.parse(event.data);
                } catch {
                    socket.close();
                    return;
                }
                if (typeof ready !== "object" || ready === null
                    || !("transport" in ready) || ready.transport !== "ready"
                    || !("version" in ready) || ready.version !== 1) {
                    socket.close();
                    return;
                }
                clearTimeout(deadline);
                this.setConnected(true);
            } else {
                this.onMessage(event.data);
            }
        });
        socket.addEventListener("close", () => {
            clearTimeout(deadline);
            if (this.socket !== socket) return;
            this.socket = undefined;
            this.setConnected(false);
            this.scheduleRetry();
        });
    }
}
