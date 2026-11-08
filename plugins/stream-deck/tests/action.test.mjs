import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

import { ControlAction } from "../dist/action.js";
import { ControlClient } from "../dist/client.js";
import { settle, useFeedbackClock } from "./helpers/feedback-clock.mjs";

useFeedbackClock();

test("SDK key handlers route commands and render confirmed state and unavailable feedback", async () => {
	const snapshot = JSON.parse(
		await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
	).messages[0];
	let receive, connect;
	const sent = [];
	const client = new ControlClient((message, connection) => {
		receive = (value) => message(JSON.stringify(value));
		connect = connection;
		return {
			start() {},
			stop() {
				connection(false);
			},
			send(value) {
				sent.push(JSON.parse(value));
				return true;
			},
		};
	});
	const action = new ControlAction(client);
	const outputs = { states: [], images: [], titles: [], alerts: 0 };
	const key = {
		id: "visible-key",
		isKey: () => true,
		async setState(value) {
			outputs.states.push(value);
		},
		async setImage(value) {
			outputs.images.push(value);
		},
		async setTitle(value) {
			outputs.titles.push(value);
		},
		async showAlert() {
			outputs.alerts++;
		},
	};
	const event = { action: key, payload: { settings: { operation: "curve.set", curve: "combined" } } };
	await action.onWillAppear(event);
	assert.match(outputs.titles.at(-1), /Offline/);
	await action.onKeyDown(event);
	assert.equal(outputs.alerts, 1);
	connect(true);
	receive(snapshot);
	await action.onDidReceiveSettings(event);
	await settle();
	await action.onKeyDown(event);
	assert.equal(sent.length, 1);
	assert.equal(sent[0].action.enabled, true);
	assert.equal(outputs.states.at(-1), 0);
	receive({
		...snapshot,
		sequence: snapshot.sequence + 1,
		curves: snapshot.curves.map((value) => (value.curve === "combined" ? { ...value, active: true } : value)),
	});
	await action.onDidReceiveSettings(event);
	await settle();
	assert.equal(outputs.states.at(-1), 1);
	assert.match(outputs.images.at(-1), /^data:image\/svg\+xml;base64,/);
	assert.match(
		Buffer.from(outputs.images.at(-1).split(",")[1], "base64").toString("utf8"),
		/<title>combined: pending<\/title>/,
	);
	receive({ version: 3, type: "response", id: sent[0].id, target: sent[0].target, status: "ok" });
	await action.onDidReceiveSettings(event);
	await settle();
	assert.match(
		Buffer.from(outputs.images.at(-1).split(",")[1], "base64").toString("utf8"),
		/<title>combined: active<\/title>/,
	);
	connect(false);
	await action.onDidReceiveSettings(event);
	await settle();
	assert.equal(outputs.states.at(-1), 0);
	assert.match(outputs.titles.at(-1), /Offline/);
	action.onWillDisappear(event);
});

test("CLI file matching resolves patched minimatch and retains include/exclude behavior", () => {
	const require = createRequire(import.meta.url);
	const cli = createRequire(require.resolve("@elgato/cli/package.json"));
	const ejs = createRequire(cli.resolve("ejs"));
	const jake = createRequire(ejs.resolve("jake"));
	const filelist = createRequire(jake.resolve("filelist"));
	assert.equal(filelist("minimatch/package.json").version, "11.0.1");
	const { FileList } = jake("filelist");
	const files = new FileList();
	files.include(new URL("../src/*.ts", import.meta.url).pathname.replace(/^\/(.:\/)/, "$1"), {
		windowsPathsNoEscape: true,
	});
	files.exclude(/[\\/]inspector\.ts$/);
	const names = files.toArray().map((value) => value.replaceAll("\\", "/"));
	assert.ok(names.some((value) => value.endsWith("/src/index.ts")));
	assert.ok(!names.some((value) => value.endsWith("/src/inspector.ts")));
});
