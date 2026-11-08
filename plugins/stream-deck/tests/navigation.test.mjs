import streamDeck from "@elgato/streamdeck";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { ControlClient } from "../dist/client.js";
import { HomeAction } from "../dist/home.js";
import { navigationFeedback, navigationSettings, PlusNavigationAction } from "../dist/navigation.js";
import { settle, useFeedbackClock } from "./helpers/feedback-clock.mjs";
import { CONTROL_VERSION } from "./helpers/versions.mjs";

useFeedbackClock();

test("hidden Home metadata describes the first bundled page and preserves its action identity", async () => {
	const manifest = JSON.parse(
		await readFile(
			new URL("../io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/manifest.json", import.meta.url),
			"utf8",
		),
	);
	const home = manifest.Actions.find((action) => action.Name === "Home");
	assert.equal(home.UUID, "io.github.rudnerbjoern.ride-forces-analyzer.home");
	assert.equal(home.VisibleInActionsList, false);
	assert.equal(home.Tooltip, "Return to the first page of the bundled Plus or Neo profile.");
});

/**
 * Create a simulated native Plus menu key and record SDK feedback.
 * @param {string} device Invoking SDK device identity.
 * @param {number} page Native page index containing the key.
 * @param {string|number} target Menu group or subgroup selected by the key.
 * @param {number} type SDK device type, defaulting to Plus.
 * @returns {object} Action event with recorded states, images, titles and alerts.
 */
function key(device, page, target, type = 7) {
	const output = { states: [], images: [], titles: [], alerts: 0 };
	return {
		output,
		action: {
			id: `${device}/${page}/${target}`,
			device: { id: device, type },
			isKey: () => true,
			async setState(value) {
				output.states.push(value);
			},
			async setImage(value) {
				output.images.push(value);
			},
			async setTitle(value) {
				output.titles.push(value);
			},
			async showAlert() {
				output.alerts++;
			},
		},
		payload: { settings: { page, target } },
	};
}

test("Home alerts once when a native profile switch rejects after sending", async (t) => {
	const warnings = t.mock.method(streamDeck.logger, "warn", () => {});
	for (const [type, profile] of [
		[7, "profiles/plus"],
		[9, "profiles/neo"],
	]) {
		let reject;
		const calls = [];
		const action = new HomeAction((...args) => {
			calls.push(args);
			return new Promise((resolve, fail) => {
				reject = fail;
			});
		});
		const event = key("device", 1, "home", type);
		const pending = action.onKeyDown(event);
		await settle();
		assert.deepEqual(calls, [["device", profile, 0]]);
		assert.equal(event.output.alerts, 0);
		const error = new Error("Profile switch rejected");
		reject(error);
		await pending;
		assert.equal(event.output.alerts, 1);
		assert.deepEqual(warnings.mock.calls.at(-1).arguments, ["Home page request failed", { type: "Error" }]);
	}
	assert.equal(warnings.mock.callCount(), 2);
});

test("menu captions follow confirmed app values and keep marker priority on every page", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const examples = JSON.parse(
		await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
	);
	let receive, connect;
	const sent = [];
	const client = new ControlClient((message, connection) => {
		receive = (value) => message(JSON.stringify(value));
		connect = connection;
		return {
			start() {},
			stop() {},
			send(value) {
				sent.push(JSON.parse(value));
				return true;
			},
		};
	});
	connect(true);
	let state = structuredClone(examples.messages[0]);
	receive(state);
	const action = new PlusNavigationAction(client, async () => {});
	const keys = ["library", "playback", "curves", "markers"].map((target) => key("plus", 0, target));
	for (const value of keys) await action.onWillAppear(value);
	assert.deepEqual(
		keys.map((value) => value.output.titles.at(-1)),
		["Library\n1/2", "Playback\nPaused", "Curves\nCalibrated", "Markers\n1 preview"],
	);
	assert.equal(client.send("play", { name: "playback.toggle" }), true);
	receive({ version: CONTROL_VERSION, type: "response", id: sent[0].id, target: sent[0].target, status: "ok" });
	await settle();
	assert.equal(keys[1].output.titles.at(-1), "Playback\nPaused", "An acknowledgement is not a changed playback state");
	state = structuredClone(state);
	state.sequence++;
	state.library.selected.index = 1;
	state.playback.playing = true;
	state.curves.find((curve) => curve.curve === "calibrated").active = false;
	receive(state);
	await settle();
	assert.deepEqual(
		keys.slice(0, 3).map((value) => value.output.titles.at(-1)),
		["Library\n2/2", "Playback\nPlaying", "Curves\nRaw"],
	);
	state.sequence++;
	state.availability = { available: false, reason: "input.focused" };
	state.markers[0].status = "failed";
	state.markers[0].error = "analysis.failed";
	state.markers[0].preview = structuredClone(state.markers[1].preview);
	state.markers[0].request_id = "failed-marker";
	state.markers[1].status = "pending";
	state.markers[1].request_id = "pending-marker";
	receive(state);
	await settle();
	for (let page = 0; page < 6; page++) {
		const feedback = navigationFeedback({ page, target: "markers" }, page, client);
		assert.equal(feedback.title, "Markers\nFailed");
		assert.match(feedback.image, /markers: failed/);
	}
	assert.equal(keys[3].output.titles.at(-1), "Markers\nFailed");
	state.sequence++;
	state.markers[0].status = "applied";
	state.markers[0].preview = null;
	state.markers[0].error = null;
	receive(state);
	await settle();
	assert.equal(keys[3].output.titles.at(-1), "Markers\nPending");
	state.sequence++;
	state.markers[1].status = "preview";
	state.markers[1].request_id = null;
	receive(state);
	await settle();
	assert.equal(keys[3].output.titles.at(-1), "Markers\n1 preview");
	state.sequence++;
	state.markers[1].preview = null;
	state.markers[1].status = "applied";
	receive(state);
	await settle();
	assert.equal(keys[3].output.titles.at(-1), "Markers\nNo preview");
	connect(false);
	await settle();
	for (const [index, title] of ["Library", "Playback", "Curves", "Markers"].entries()) {
		assert.equal(keys[index].output.titles.at(-1), `${title}\nOffline`);
	}
});

test("Plus navigation uses only confirmed appearances, including swipes, and remembers groups per device", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	const calls = [];
	const action = new PlusNavigationAction(new ControlClient(), async (...args) => {
		calls.push(args);
	});
	const initial = key("a", 0, "playback");
	await action.onWillAppear(initial);
	await action.onKeyDown(initial);
	assert.deepEqual(calls, [["a", "profiles/plus", 1]]);
	assert.equal(initial.output.states.at(-1), 0, "Sending a request must not confirm its target");
	assert.doesNotMatch(Buffer.from(initial.output.images.at(-1).split(",")[1], "base64").toString(), /#64d6ff/);
	action.onWillDisappear(initial);
	// This appearance can be caused by either a native swipe or a requested switch.
	const selection = key("a", 2, "playback");
	await action.onWillAppear(selection);
	assert.equal(selection.output.states.at(-1), 1);
	assert.match(Buffer.from(selection.output.images.at(-1).split(",")[1], "base64").toString(), /#64d6ff/);
	await action.onKeyDown(selection);
	assert.equal(calls.length, 1, "Repeated selection of the visible group must not switch again");
	await action.onKeyDown(key("a", 2, "library"));
	assert.deepEqual(calls.at(-1), ["a", "profiles/plus", 0]);
	action.onWillDisappear(selection);
	await action.onWillAppear(initial);
	await action.onKeyDown(initial);
	assert.deepEqual(calls.at(-1), ["a", "profiles/plus", 2]);
	const other = key("b", 0, "playback");
	await action.onWillAppear(other);
	await action.onKeyDown(other);
	assert.deepEqual(calls.at(-1), ["b", "profiles/plus", 1]);
	const markerView = key("a", 5, "markers");
	await action.onWillAppear(markerView);
	await action.onKeyDown(key("a", 5, 4));
	assert.deepEqual(calls.at(-1), ["a", "profiles/plus", 4]);
	await action.onWillAppear(key("a", 0, "library"));
	await action.onKeyDown(key("a", 0, "markers"));
	assert.deepEqual(calls.at(-1), ["a", "profiles/plus", 5], "Only appearance updates remembered subgroups");
	await action.onKeyDown(key("b", 0, "markers"));
	assert.deepEqual(calls.at(-1), ["b", "profiles/plus", 4]);
	assert.equal(navigationFeedback({ page: 0, target: "library" }, undefined).selected, false);
});

test("Plus navigation rejects invalid settings/devices and does not confirm failed or overlapping requests", async (t) => {
	t.mock.method(streamDeck.logger, "info", () => {});
	t.mock.method(streamDeck.logger, "warn", () => {});
	for (const settings of [
		{},
		{ page: "1", target: "library" },
		{ page: true, target: "library" },
		{ page: 6, target: "library" },
		{ page: -1, target: "library" },
		{ page: 1.5, target: "library" },
		{ page: 0, target: 2 },
		{ page: 1, target: 5 },
		{ page: 4, target: 2 },
		{ page: 0, target: "unknown" },
	]) {
		assert.equal(navigationSettings(settings), undefined);
	}
	for (const [page, target] of [
		[0, "library"],
		[1, 2],
		[2, 1],
		[4, 5],
		[5, 4],
	]) {
		assert.deepEqual(navigationSettings({ page, target }), { page, target });
	}
	let finish;
	const calls = [];
	const action = new PlusNavigationAction(new ControlClient(), (...args) => {
		calls.push(args);
		return new Promise((resolve, reject) => {
			finish = { resolve, reject };
		});
	});
	const initial = key("a", 0, "playback");
	await action.onWillAppear(initial);
	const pending = action.onKeyDown(initial);
	await action.onKeyDown(initial);
	assert.equal(calls.length, 1, "Do not queue repeated presses while sending");
	finish.reject(new Error("Simulated SDK send failure"));
	await pending;
	assert.equal(initial.output.alerts, 1);
	assert.equal(initial.output.states.at(-1), 0);
	const retry = action.onKeyDown(initial);
	assert.equal(calls.length, 2, "A failed request remains retryable");
	finish.resolve();
	await retry;
	assert.equal(initial.output.states.at(-1), 0, "A resolved SDK promise is not a page acknowledgement");
	const neo = key("neo", 0, "playback", 9);
	await action.onWillAppear(neo);
	await action.onKeyDown(neo);
	assert.equal(neo.output.alerts, 1);
	assert.equal(neo.output.states.length, 0);
	assert.equal(calls.length, 2);
});
