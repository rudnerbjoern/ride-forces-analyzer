import streamDeck from "@elgato/streamdeck";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { setImmediate } from "node:timers/promises";

import { ControlAction } from "../dist/action.js";
import { ControlClient } from "../dist/client.js";
import { StepMode } from "../dist/device-controls.js";
import { DialControlAction } from "../dist/dial-action.js";
import { InfoBarAction } from "../dist/infobar-action.js";
import { StepModeAction } from "../dist/mode-action.js";
import { PlusNavigationAction } from "../dist/navigation.js";
import { useFeedbackClock } from "./helpers/feedback-clock.mjs";
import { CONTROL_VERSION } from "./helpers/versions.mjs";

const fixture = JSON.parse(
	await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
).messages[0];
useFeedbackClock();

test("rapid local Step size changes preserve every input while their actual visual calls share the budget", async (t) => {
	const mode = new StepMode();
	const handler = new StepModeAction(mode);
	const calls = [];
	const action = { id: "mode", device: { id: "plus" }, isKey: () => true };
	for (const method of ["setState", "setImage", "setTitle"])
		action[method] = async (value) => {
			calls.push({ method, value, time: Date.now() });
		};
	const event = { action, payload: { settings: {} } };
	await handler.onWillAppear(event);
	for (let index = 0; index < 20; index++) await handler.onKeyDown(event);
	assert.equal(mode.samples("plus"), 20, "Input processing must not wait for visual transmission");
	await advance(t, 1000);
	assert.equal(calls.findLast((call) => call.method === "setState").value, 2);
	assert.match(calls.findLast((call) => call.method === "setTitle").value, /Coarse/);
	for (const call of calls)
		assert.ok(calls.filter((other) => other.time > call.time - 1000 && other.time <= call.time).length <= 10);
	const before = calls.length;
	handler.onWillDisappear(event);
	mode.toggle("plus");
	await advance(t, 1000);
	assert.equal(calls.length, before, "A vanished Step size key receives no delayed calls");
});

/**
 * Count actual visual API invocations for four visible surface kinds.
 * @returns {Promise<object>} Connected actions, recorded SDK calls and transport helpers.
 */
async function harness() {
	let receive, connect;
	const commands = [];
	const client = new ControlClient((message, connection) => {
		receive = (value) => message(JSON.stringify(value));
		connect = connection;
		return {
			start() {},
			stop() {},
			send(value) {
				commands.push(JSON.parse(value));
				return true;
			},
		};
	});
	connect(true);
	let state = structuredClone(fixture);
	receive(state);
	const calls = [];
	const alerts = [];
	const kinds = [
		["key", new ControlAction(client), { operation: "position.step", steps: 1 }],
		["dial", new DialControlAction(client, new StepMode()), { control: "position" }],
		["navigation", new PlusNavigationAction(client, async () => {}), { page: 0, target: "library" }],
		["bar", new InfoBarAction(client), { section: "playback" }],
	];
	const surfaces = kinds.map(([kind, handler, settings]) => {
		const action = {
			id: kind,
			device: { id: "device", type: kind === "bar" ? 9 : 7 },
			isKey: () => kind === "key" || kind === "navigation",
			isDial: () => kind === "dial",
			isNeoInfobar: () => kind === "bar",
			async setTriggerDescription() {},
			async showAlert() {
				alerts.push({ kind, time: Date.now() });
			},
		};
		for (const method of ["setImage", "setTitle", "setState", "setFeedback", "setFeedbackLayout"]) {
			action[method] = async (value) => {
				calls.push({ kind, method, value, time: Date.now() });
			};
		}
		return { kind, handler, event: { action, payload: { settings } } };
	});
	for (const surface of surfaces) await surface.handler.onWillAppear(surface.event);
	return {
		client,
		commands,
		calls,
		alerts,
		surfaces,
		receive,
		connect,
		publish(index, update) {
			state = structuredClone(state);
			state.sequence++;
			state.playback.position.sample = index;
			state.playback.position.label = `00:${String(index).padStart(2, "0")}.00`;
			state.library.count = index + 2;
			update?.(state);
			receive(state);
		},
	};
}

/**
 * Advance the virtual clock after pending SDK completions have settled.
 * @param {object} t Node test context owning the virtual timers.
 * @param {number} milliseconds Elapsed virtual time to simulate.
 */
async function advance(t, milliseconds) {
	await setImmediate();
	t.mock.timers.tick(milliseconds);
	await setImmediate();
}

/**
 * Check every rolling one-second window using actual SDK invocation timestamps.
 * @param {object[]} calls Captured visual API invocations across all surface kinds.
 */
function assertBudget(calls) {
	for (const kind of ["key", "dial", "navigation", "bar"]) {
		const own = calls.filter((call) => call.kind === kind);
		for (const call of own) {
			assert.ok(
				own.filter((other) => other.time > call.time - 1000 && other.time <= call.time).length <= 10,
				`${kind} exceeded ten visual API calls in a rolling second ending at ${call.time}`,
			);
		}
	}
}

/**
 * Check that all four surfaces have caught up to the last confirmed snapshot.
 * @param {object[]} calls Captured visual API invocations.
 * @param {number} index Last published position and Library count offset.
 */
function assertLatest(calls, index) {
	const last = (kind, method) => calls.findLast((call) => call.kind === kind && call.method === method)?.value;
	assert.equal(last("key", "setTitle"), `Pos. 1\n00:${String(index).padStart(2, "0")}.00`);
	assert.match(last("dial", "setFeedback").value, new RegExp(`#${index} `));
	assert.equal(last("navigation", "setTitle"), `Library\n1/${index + 2}`);
	assert.match(last("bar", "setFeedback").value, new RegExp(`#${index} `));
}

test("twenty distinct snapshots coalesce to the latest frame within the actual per-surface API budget", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const initial = h.calls.length;
	for (let index = 1; index <= 20; index++) {
		h.publish(index);
		await setImmediate();
	}
	assert.equal(h.calls.length, initial, "A burst must not stream intermediate frames before its slot");
	await advance(t, 100);
	assertLatest(h.calls, 20);
	assertBudget(h.calls);
	const count = h.calls.length;
	h.publish(20);
	await advance(t, 2000);
	assert.equal(h.calls.length, count, "Unchanged feedback must still be deduplicated");
});

test("position-only changes send only key/menu titles and changed dial/InfoBar text fields", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const before = h.calls.length;
	h.publish(51);
	await advance(t, 100);
	const changed = h.calls.slice(before);
	assert.deepEqual(
		changed.filter((call) => call.kind === "key").map((call) => call.method),
		["setTitle"],
	);
	assert.deepEqual(
		changed.filter((call) => call.kind === "navigation").map((call) => call.method),
		["setTitle"],
	);
	for (const kind of ["dial", "bar"]) {
		const calls = changed.filter((call) => call.kind === kind);
		assert.deepEqual(
			calls.map((call) => call.method),
			["setFeedback"],
		);
		assert.deepEqual(Object.keys(calls[0].value), ["value"]);
	}
	assertLatest(h.calls, 51);
	assertBudget(h.calls);
});

test("returning to a key state reuses its previously sent state-specific image and title", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const key = h.surfaces.find((surface) => surface.kind === "key");
	await key.handler.onDidReceiveSettings({
		...key.event,
		payload: { settings: { operation: "curve.set", curve: "combined" } },
	});
	await advance(t, 1000);
	h.publish(50, (state) => {
		state.curves.find((curve) => curve.curve === "combined").active = true;
	});
	await advance(t, 1000);
	const before = h.calls.length;
	h.publish(50, (state) => {
		state.curves.find((curve) => curve.curve === "combined").active = false;
	});
	await advance(t, 1000);
	const changed = h.calls.slice(before).filter((call) => call.kind === "key");
	assert.deepEqual(
		changed.map(({ method, value }) => ({ method, value })),
		[{ method: "setState", value: 0 }],
	);
	assertBudget(h.calls);
});

test("dial pending and failed states update status artwork while retaining unchanged function images", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const dial = h.surfaces.find((surface) => surface.kind === "dial");
	const before = h.calls.length;
	await dial.handler.onDialRotate({ ...dial.event, payload: { ...dial.event.payload, ticks: 1 } });
	await advance(t, 1000);
	const pending = h.calls.slice(before).filter((call) => call.kind === "dial");
	assert.deepEqual(
		pending.map((call) => call.method),
		["setFeedback"],
	);
	assert.deepEqual(Object.keys(pending[0].value).sort(), ["band", "status", "statusIcon"]);
	assert.match(pending[0].value.status.value, /Pending/);
	const command = h.commands.at(-1);
	const count = h.calls.length;
	h.receive({
		version: CONTROL_VERSION,
		type: "response",
		id: command.id,
		target: command.target,
		status: "error",
		code: "command.unavailable",
		reason: "application.background",
	});
	assert.equal(h.alerts.at(-1).kind, "dial");
	await advance(t, 1000);
	const failed = h.calls.slice(count).filter((call) => call.kind === "dial");
	assert.deepEqual(
		failed.map((call) => call.method),
		["setFeedback"],
	);
	assert.deepEqual(Object.keys(failed[0].value).sort(), ["band", "status", "statusIcon"]);
	assert.match(failed[0].value.status.value, /Failed/);
	assert.notEqual(failed[0].value.band, pending[0].value.band);
	assert.notEqual(failed[0].value.statusIcon, pending[0].value.statusIcon);
	assertBudget(h.calls);
});

test("a changed dial function image updates both its configuration image and the independent touch icon", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const dial = h.surfaces.find((surface) => surface.kind === "dial");
	await dial.handler.onDidReceiveSettings({ ...dial.event, payload: { settings: { control: "playback" } } });
	await advance(t, 1000);
	const before = h.calls.length;
	h.publish(50, (state) => {
		state.playback.playing = true;
	});
	await advance(t, 1000);
	const changed = h.calls.slice(before).filter((call) => call.kind === "dial");
	assert.deepEqual(
		changed.map((call) => call.method),
		["setImage", "setFeedback"],
	);
	assert.equal(changed[0].value, changed[1].value.icon);
	assert.match(Buffer.from(changed[0].value.split(",")[1], "base64").toString(), /<title>pause<\/title>/);
	assert.equal(Object.hasOwn(changed[1].value, "background"), false);
	assertBudget(h.calls);
});

test("layout changes repaint static fields even when their values matched the old layout", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const dial = h.surfaces.find((surface) => surface.kind === "dial");
	const original = h.calls.find((call) => call.kind === "dial" && call.method === "setFeedback").value;
	const before = h.calls.length;
	await dial.handler.onDidReceiveSettings({
		...dial.event,
		payload: { settings: { control: "selection", boundary: "start" } },
	});
	await advance(t, 1000);
	const changed = h.calls.slice(before).filter((call) => call.kind === "dial");
	assert.deepEqual(
		changed.map((call) => call.method),
		["setFeedbackLayout", "setImage", "setFeedback"],
	);
	assert.equal(changed[0].value, "layouts/plus.json");
	assert.equal(changed[2].value.background, original.background);
	assert.equal(changed[2].value.band, original.band);
	assert.equal(changed[2].value.statusIcon, original.statusIcon);
	assert.ok(Object.hasOwn(changed[2].value, "detail"));
	assert.deepEqual(Object.keys(changed[2].value).sort(), [...Object.keys(original), "detail"].sort());
	assertBudget(h.calls);
});

test("a coalesced reconnect repaints every necessary field even if the final snapshot is unchanged", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const initial = [...h.calls];
	const before = h.calls.length;
	h.connect(false);
	h.connect(true);
	h.publish(50, (state) => {
		state.library.count = fixture.library.count;
		state.playback.position = structuredClone(fixture.playback.position);
	});
	await advance(t, 1000);
	for (const kind of ["key", "dial", "navigation", "bar"]) {
		const expected = initial.filter((call) => call.kind === kind).map(({ method, value }) => ({ method, value }));
		const actual = h.calls
			.slice(before)
			.filter((call) => call.kind === kind)
			.map(({ method, value }) => ({ method, value }));
		assert.deepEqual(actual, expected, `${kind} must repaint after reconnect even without a visible Offline frame`);
	}
	assertBudget(h.calls);
});

test("a layout change interrupted by a return to the old values still repaints the restored layout", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const dial = h.surfaces.find((surface) => surface.kind === "dial");
	const original = h.calls.find((call) => call.kind === "dial" && call.method === "setFeedback").value;
	const sendLayout = dial.event.action.setFeedbackLayout;
	let release;
	const delayed = new Promise((resolve) => {
		release = resolve;
	});
	t.mock.method(dial.event.action, "setFeedbackLayout", async (layout) => {
		await sendLayout(layout);
		if (layout === "layouts/plus.json") await delayed;
	});
	await dial.handler.onDidReceiveSettings({
		...dial.event,
		payload: { settings: { control: "selection", boundary: "start" } },
	});
	await advance(t, 100);
	await dial.handler.onDidReceiveSettings(dial.event);
	const before = h.calls.length;
	release();
	await advance(t, 1000);
	const changed = h.calls.slice(before).filter((call) => call.kind === "dial");
	assert.deepEqual(
		changed.map((call) => call.method),
		["setFeedbackLayout", "setImage", "setFeedback"],
	);
	assert.equal(changed[0].value, "layouts/plus-compact.json");
	assert.deepEqual(changed[2].value, original);
	assertBudget(h.calls);
});

test("a rejected field update remains pending for the next identical state instead of entering the sent cache", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	t.mock.method(console, "error", () => {});
	const h = await harness();
	const dial = h.surfaces.find((surface) => surface.kind === "dial");
	const send = dial.event.action.setFeedback;
	let fail = true;
	t.mock.method(dial.event.action, "setFeedback", async (value) => {
		if (fail) {
			fail = false;
			throw new Error("Feedback send rejected");
		}
		await send(value);
	});
	h.publish(51);
	await advance(t, 1000);
	const before = h.calls.length;
	h.publish(51);
	await advance(t, 1000);
	const changed = h.calls.slice(before).filter((call) => call.kind === "dial");
	assert.deepEqual(
		changed.map((call) => call.method),
		["setFeedback"],
	);
	assert.deepEqual(Object.keys(changed[0].value), ["value"]);
	assert.match(changed[0].value.value, /#51 /);
	assertBudget(h.calls);
});

test("continuous changing feedback respects every rolling window and eventually publishes the final state", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	for (let index = 1; index <= 120; index++) {
		h.publish(index);
		await advance(t, 25);
	}
	await advance(t, 1000);
	assertBudget(h.calls);
	assertLatest(h.calls, 120);
	for (const kind of ["key", "dial", "navigation", "bar"]) {
		assert.ok(
			h.calls.filter((call) => call.kind === kind).length > 10,
			`${kind} must keep updating beyond its first budget window`,
		);
	}
	console.log(
		"Measured visual API calls over 4 virtual seconds:",
		Object.fromEntries(
			["key", "dial", "navigation", "bar"].map((kind) => {
				const calls = h.calls.filter((call) => call.kind === kind);
				return [
					kind,
					{
						total: calls.length,
						maxPerSecond: Math.max(
							...calls.map(
								(call) => calls.filter((other) => other.time > call.time - 1000 && other.time <= call.time).length,
							),
						),
					},
				];
			}),
		),
	);
});

test("slow SDK completion cannot publish obsolete values after the target clears or block another surface", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const key = h.surfaces.find((surface) => surface.kind === "key");
	let release;
	const delayed = new Promise((resolve) => {
		release = resolve;
	});
	const setTitle = key.event.action.setTitle;
	t.mock.method(key.event.action, "setTitle", async (value) => {
		await setTitle(value);
		await delayed;
	});
	h.publish(88);
	await advance(t, 100);
	assert.match(h.calls.findLast((call) => call.kind === "bar" && call.method === "setFeedback").value.value, /#88 /);
	const before = h.calls.length;
	h.connect(false);
	assert.equal(h.client.state, undefined);
	release();
	await advance(t, 1000);
	for (const call of h.calls.slice(before).filter((call) => call.kind === "key")) {
		if (call.method === "setTitle") assert.match(call.value, /Offline/);
		if (call.method === "setImage")
			assert.match(Buffer.from(call.value.split(",")[1], "base64").toString(), /disconnected/);
	}
	assert.match(h.calls.findLast((call) => call.kind === "key" && call.method === "setTitle").value, /Offline/);
	assertBudget(h.calls);
});

test("commands and failure alerts remain immediate while queued feedback uses the newest target", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	const key = h.surfaces.find((surface) => surface.kind === "key");
	const dial = h.surfaces.find((surface) => surface.kind === "dial");
	for (let index = 1; index <= 12; index++) {
		h.publish(index);
		await advance(t, 25);
	}
	for (const surface of [key, dial]) {
		if (surface.kind === "key") await surface.handler.onKeyDown(surface.event);
		else await surface.handler.onDialRotate({ ...surface.event, payload: { ...surface.event.payload, ticks: 1 } });
		const command = h.commands.at(-1);
		h.receive({
			version: CONTROL_VERSION,
			type: "response",
			id: command.id,
			target: command.target,
			status: "error",
			code: "command.unavailable",
			reason: "application.background",
		});
		assert.equal(h.alerts.at(-1).kind, surface.kind);
		assert.equal(h.alerts.at(-1).time, Date.now(), "Failure notification must not wait for visual feedback");
	}
	assert.equal(h.commands.length, 2);
	const old = h.commands[0];
	h.publish(99, (state) => {
		state.target.window_id = "replacement";
	});
	assert.equal(h.client.state.target.window_id, "replacement");
	h.receive({
		version: CONTROL_VERSION,
		type: "response",
		id: old.id,
		target: old.target,
		status: "error",
		code: "command.unavailable",
		reason: "application.background",
	});
	assert.equal(h.alerts.length, 2, "A late old-target response cannot alert the replacement target");
	await advance(t, 1000);
	assertLatest(h.calls, 99);
	assertBudget(h.calls);
});

test("disconnect clears the target immediately and replaces queued values with Offline without replay", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	for (let index = 1; index <= 12; index++) {
		h.publish(index);
		await advance(t, 25);
	}
	h.publish(99);
	const before = h.calls.length;
	h.connect(false);
	assert.equal(h.client.state, undefined);
	assert.equal(h.client.send("key", { name: "playback.toggle" }), false);
	await advance(t, 1000);
	for (const call of h.calls.slice(before)) {
		if (call.method === "setTitle") assert.match(call.value, /Offline/);
		if (call.method === "setFeedback") assert.match(JSON.stringify(call.value), /Offline/);
	}
	assert.equal(h.commands.length, 0);
	assertBudget(h.calls);
});

test("disappearance cancels queued visuals and reappearance keeps the action's remaining call budget", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const h = await harness();
	for (let index = 1; index <= 12; index++) {
		h.publish(index);
		await advance(t, 25);
	}
	h.publish(99);
	const before = h.calls.length;
	for (const surface of h.surfaces) surface.handler.onWillDisappear(surface.event);
	await advance(t, 100);
	assert.equal(h.calls.length, before, "Vanished actions must not receive delayed SDK calls");
	for (const surface of h.surfaces) await surface.handler.onWillAppear(surface.event);
	await advance(t, 1000);
	assertLatest(h.calls, 99);
	assertBudget(h.calls);
});
