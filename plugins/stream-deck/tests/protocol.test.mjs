import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { PROTOCOL_VERSION } from "../dist/protocol.js";

test("shared wire examples satisfy the plugin's strict command and feedback types", async () => {
	const examples = JSON.parse(
		await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
	);
	const directory = await mkdtemp(fileURLToPath(new URL("../../../.tmp/stream-deck-contract-", import.meta.url)));
	const filename = path.join(directory, "examples.mts");
	const protocol = fileURLToPath(new URL("../src/protocol.ts", import.meta.url)).replaceAll("\\", "/");
	const lines = [`import type { Command, ServerMessage, ConnectionState } from ${JSON.stringify(protocol)};`];
	for (const [index, action] of examples.actions.entries()) {
		const command = {
			version: PROTOCOL_VERSION,
			type: "command",
			id: `request-${index}`,
			target: examples.target,
			action,
		};
		lines.push(`export const command${index} = ${JSON.stringify(command)} satisfies Command;`);
	}
	for (const [index, message] of examples.messages.entries()) {
		lines.push(`export const message${index} = ${JSON.stringify(message)} satisfies ServerMessage;`);
	}
	lines.push('export const disconnected = "disconnected" satisfies ConnectionState;');
	for (const action of [
		{ name: "unknown" },
		{ name: "marker.apply" },
		{ name: "library.move", direction: true },
		{ name: "position.step", steps: 2 },
		{ name: "curve.set", curve: "combined", enabled: "yes" },
		{ name: "library.filter.set", filter: "ride", value: null },
		{ name: "library.filter.set", filter: "park", value: true },
		{ name: "library.filter.set", filter: "park", value: 12 },
		{ name: "library.filter.set", filter: "status" },
	]) {
		const command = { version: PROTOCOL_VERSION, type: "command", id: "invalid", target: examples.target, action };
		lines.push(
			"// @ts-expect-error Reject incompatible command shapes.",
			`export const invalid${lines.length} = ${JSON.stringify(command)} satisfies Command;`,
		);
	}
	lines.push(
		"// @ts-expect-error Reject unknown application protocol versions.",
		`export const incompatible = ${JSON.stringify({ ...examples.messages[0], version: 99 })} satisfies ServerMessage;`,
	);
	try {
		await writeFile(filename, lines.join("\n"));
		const configuration = path.join(directory, "tsconfig.json");
		await writeFile(
			configuration,
			JSON.stringify({
				compilerOptions: {
					strict: true,
					exactOptionalPropertyTypes: true,
					noUncheckedIndexedAccess: true,
					noEmit: true,
					allowImportingTsExtensions: true,
					module: "NodeNext",
					moduleResolution: "NodeNext",
					target: "ES2024",
					types: [],
				},
				files: [filename],
			}),
		);
		const compiler = fileURLToPath(new URL("../../../node_modules/typescript/bin/tsc", import.meta.url));
		const { stdout, stderr } = await promisify(execFile)(process.execPath, [compiler, "--project", configuration]);
		assert.equal(stdout + stderr, "");
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});
