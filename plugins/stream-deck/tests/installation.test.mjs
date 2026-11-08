import assert from "node:assert/strict";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { pluginOutput } from "../scripts/artifact-path.mjs";
import { copyInstallation } from "../scripts/link-plugin.mjs";

test("the local deployment survives replacement of build output without installing software", async () => {
	const directory = await mkdtemp(fileURLToPath(new URL("../../../.tmp/stream-deck-install-", import.meta.url)));
	const build = path.join(directory, "build.sdPlugin");
	const installed = path.join(directory, "installed.sdPlugin");
	try {
		await cp(pluginOutput, build, {
			recursive: true,
			filter: (filename) => path.relative(pluginOutput, filename).split(path.sep)[0] !== "logs",
		});
		await mkdir(path.join(build, "logs"));
		await writeFile(path.join(build, "logs/test.log"), "test log");
		await copyInstallation(build, installed);
		await assert.rejects(readFile(path.join(installed, "logs/test.log")), { code: "ENOENT" });
		const original = await readFile(path.join(build, "bin/plugin.js"));
		await writeFile(path.join(build, "bin/plugin.js"), "replaced build");
		await rm(build, { recursive: true, force: true });
		assert.deepEqual(await readFile(path.join(installed, "bin/plugin.js")), original);
		assert.match(await readFile(path.join(installed, "LICENSE"), "utf8"), /GNU GENERAL PUBLIC LICENSE/);
		assert.ok((await readFile(path.join(installed, "profiles/plus.streamDeckProfile"))).length > 0);
		assert.ok((await readFile(path.join(installed, "profiles/neo.streamDeckProfile"))).length > 0);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});
