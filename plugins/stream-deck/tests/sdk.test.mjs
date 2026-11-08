import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
import { pathToFileURL } from "node:url";

// Resolve the SDK's actual schema consumer, including non-hoisted dependencies.
const require = createRequire(import.meta.url);
const sdk = createRequire(require.resolve("@elgato/streamdeck"));
const utils = createRequire(sdk.resolve("@elgato/utils"));
const { OptionGroup } = await import(pathToFileURL(sdk.resolve("@elgato/utils")).href);
const { JsonRpcRequest } = await import(pathToFileURL(sdk.resolve("@elgato/utils/rpc")).href);

test("SDK schema consumer resolves the patched Zod override", () => {
	const { overrides } = require("../../../package.json");

	assert.equal(utils("zod/package.json").version, overrides["@elgato/utils"].zod);
});

test("SDK option schemas retain nested groups and reject invalid values", () => {
	const group = {
		type: "option-group",
		label: "Explorer",
		options: [{ type: "option", label: "Playback", value: "playback" }],
	};

	assert.deepEqual(OptionGroup.parse(group), group);
	assert.equal(OptionGroup.safeParse({ ...group, options: [{ value: {} }] }).success, false);
});

test("SDK RPC schemas retain command parameters and reject invalid methods", () => {
	const request = { jsonrpc: "2.0", method: "test", id: "1", params: { value: 1 } };

	assert.deepEqual(JsonRpcRequest.parse(request), request);
	assert.equal(JsonRpcRequest.safeParse({ ...request, method: 1 }).success, false);
});
