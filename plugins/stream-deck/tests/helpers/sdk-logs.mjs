import streamDeck from "@elgato/streamdeck";
import { beforeEach } from "node:test";

/** Capture unit-test diagnostics without creating SDK log artifacts outside .tmp. */
export function useSdkLogs() {
	beforeEach((t) => {
		for (const level of ["info", "warn", "error"]) t.mock.method(streamDeck.logger, level, () => {});
	});
}
