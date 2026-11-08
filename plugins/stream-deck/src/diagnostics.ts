import streamDeck from "@elgato/streamdeck";

const errorNames = new Set([
	"Error",
	"TypeError",
	"RangeError",
	"SyntaxError",
	"ReferenceError",
	"TimeoutError",
	"ConnectionError",
]);
const errorCodes = new Set(["ENOENT", "EACCES", "EPERM", "ECONNREFUSED", "ECONNRESET", "ETIMEDOUT", "EPIPE"]);

/**
 * Log an operation failure without serializing messages, stacks, payloads or credentials.
 * @param operation Fixed application-owned description of the failed operation.
 * @param error Untrusted failure supplied by the SDK, transport or renderer.
 * @param level Severity appropriate to the recoverable native request or unexpected failure.
 */
export function logFailure(operation: string, error: unknown, level: "error" | "warn" = "error"): void {
	const type = error instanceof Error && errorNames.has(error.name) ? error.name : "UnknownError";
	const code = typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
	const safeCode =
		(typeof code === "number" && Number.isSafeInteger(code)) || (typeof code === "string" && errorCodes.has(code));
	streamDeck.logger[level](operation, { type, ...(safeCode ? { code } : {}) });
}
