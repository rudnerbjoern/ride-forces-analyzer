import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, renameSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

import { pluginOutput } from "./artifact-path.mjs";

const { values } = parseArgs({
	options: {
		output: { type: "string", default: fileURLToPath(new URL("../../../.tmp/stream-deck-package/", import.meta.url)) },
		force: { type: "boolean", default: false },
	},
});
const destination = path.resolve(values.output, "Ride-Forces-Analyzer.streamDeckPlugin");
if (existsSync(destination) && !values.force) {
	throw new Error("Plugin archive already exists; use --force to replace it deliberately");
}
mkdirSync(values.output, { recursive: true });
const require = createRequire(import.meta.url);
const cli = path.join(path.dirname(require.resolve("@elgato/cli/package.json")), "bin/streamdeck.mjs");
const result = spawnSync(
	process.execPath,
	[
		cli,
		"pack",
		pluginOutput,
		"--output",
		values.output,
		"--no-update-check",
		"--no-file-list",
		...(values.force ? ["--force"] : []),
	],
	{ stdio: "inherit" },
);
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status ?? 1);
renameSync(path.join(values.output, "io.github.rudnerbjoern.ride-forces-analyzer.streamDeckPlugin"), destination);
console.log(`Installer: ${destination}`);
