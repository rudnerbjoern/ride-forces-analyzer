import { beforeEach } from "node:test";
import { setImmediate } from "node:timers/promises";

import { useSdkLogs } from "./sdk-logs.mjs";

let clock;

/** Install a fresh virtual feedback clock for each sequential action test. */
export function useFeedbackClock() {
	useSdkLogs();
	beforeEach((t) => {
		clock = t.mock.timers;
		clock.enable({ apis: ["Date", "setTimeout"], now: 10000 });
	});
}

/** Let pending SDK promises complete and give the latest frame a full transmission window. */
export async function settle() {
	await setImmediate();
	clock.tick(1000);
	await setImmediate();
}
