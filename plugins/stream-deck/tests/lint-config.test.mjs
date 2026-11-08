import { ESLint } from "eslint";
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { resolveConfig } from "prettier";

const workspace = fileURLToPath(new URL("../", import.meta.url));
const root = path.resolve(workspace, "../..");

test("Elgato lint rules apply to plugin code and ignore external code", async () => {
	const eslint = new ESLint({ cwd: root, overrideConfigFile: path.join(workspace, "eslint.config.js") });
	for (const name of ["src/action.ts", "scripts/build-plugin.mjs", "tests/action.test.mjs"]) {
		const config = await eslint.calculateConfigForFile(path.join(workspace, name));
		assert.equal(config.rules["jsdoc/require-jsdoc"][0], 1);
		assert.equal(config.rules.indent[1], "tab");
	}
	for (const name of ["scripts/generate_stream_deck_screenshots.py", "tests/docs/documentation.test.mjs"]) {
		const config = await eslint.calculateConfigForFile(path.join(root, name));
		assert.equal(config?.rules?.["jsdoc/require-jsdoc"], undefined);
		assert.equal(config?.rules?.indent, undefined);
	}
});

test("Elgato Prettier settings stop at the plugin workspace", async () => {
	const config = await resolveConfig(path.join(workspace, "src/action.ts"), { editorconfig: true });
	assert.equal(config.useTabs, true);
	assert.equal(config.printWidth, 120);
	const jsonConfig = await resolveConfig(path.join(workspace, "package.json"), { editorconfig: true });
	assert.equal(jsonConfig.useTabs, false);
	assert.equal(jsonConfig.tabWidth, 4);
	assert.equal(await resolveConfig(path.join(root, "tests/docs/documentation.test.mjs")), null);
});
