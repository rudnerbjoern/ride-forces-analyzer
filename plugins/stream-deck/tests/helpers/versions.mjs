import { readFileSync } from "node:fs";

// Read each wire version independently, even when their numeric values coincide.
const control = readFileSync(new URL("../../src/protocol.ts", import.meta.url), "utf8");
const transport = readFileSync(
	new URL("../../../../src/ride_forces_analyzer/runtime/stream_deck.py", import.meta.url),
	"utf8",
);
export const CONTROL_VERSION = Number(control.match(/^export const PROTOCOL_VERSION = (\d+);$/m)[1]);
export const TRANSPORT_VERSION = Number(transport.match(/^TRANSPORT_VERSION = (\d+)$/m)[1]);
