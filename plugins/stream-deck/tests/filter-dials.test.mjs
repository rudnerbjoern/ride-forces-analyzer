import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { ControlAction } from "../dist/action.js";
import { ControlClient } from "../dist/client.js";
import { dialSettings, StepMode } from "../dist/device-controls.js";
import { DialControlAction } from "../dist/dial-action.js";
import { settle, useFeedbackClock } from "./helpers/feedback-clock.mjs";

const fixture = JSON.parse(
	await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
).messages[0];
useFeedbackClock();

/**
 * Create a simulated Park/Status dial or Reset filters key.
 * @param {string} filter Park, status or reset binding for the simulated action.
 * @param {string} device SDK device identity used to isolate filter proposals.
 * @returns {object} Event, action and recorded feedback/alerts.
 */
function surface(filter, device = "plus") {
	const output = { feedback: [], current: {}, alerts: 0 };
	const settings = filter === "reset" ? { operation: "library.filter.reset" } : { control: "filter", filter };
	return {
		output,
		payload: { settings },
		action: {
			id: `${device}/${filter}`,
			device: { id: device, type: 7 },
			isDial: () => true,
			async setFeedbackLayout() {
				output.current = {};
			},
			async setTriggerDescription() {},
			async setImage() {},
			async setFeedback(value) {
				output.current = { ...output.current, ...value };
				output.feedback.push(output.current);
			},
			async showAlert() {
				output.alerts++;
			},
		},
	};
}

/**
 * Prepare connected filter actions and confirmed options for gesture tests.
 * @returns {Promise<object>} Filter actions, command capture and state/response helpers.
 */
async function harness() {
	let receive, connect;
	let deliver = true;
	const sent = [];
	const client = new ControlClient((message, connection) => {
		receive = (value) => message(JSON.stringify(value));
		connect = connection;
		return {
			start() {},
			stop() {},
			send(value) {
				if (!deliver) return false;
				sent.push(JSON.parse(value));
				return true;
			},
		};
	});
	const mode = new StepMode();
	const dials = new DialControlAction(client, mode);
	const keys = new ControlAction(client, (device) => dials.resetFilters(device));
	let state = structuredClone(fixture);
	const publish = async (change) => {
		state = structuredClone(state);
		change?.(state);
		state.sequence++;
		receive(state);
		await settle();
	};
	const reply = async (status = "ok", code = "command.unavailable") => {
		const command = sent.at(-1);
		receive({
			version: 3,
			type: "response",
			id: command.id,
			target: command.target,
			status,
			...(status === "error" ? { code, reason: null } : {}),
		});
		await settle();
	};
	connect(true);
	await publish();
	const park = surface("park"),
		status = surface("status");
	await dials.onWillAppear(park);
	await dials.onWillAppear(status);
	const rotate = async (dial, ticks) => {
		await dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks } });
		await settle();
	};
	const press = async (dial) => {
		await dials.onDialDown(dial);
		await settle();
	};
	const touch = async (dial) => {
		await dials.onTouchTap(dial);
		await settle();
	};
	return {
		client,
		dials,
		keys,
		mode,
		park,
		status,
		sent,
		publish,
		reply,
		rotate,
		press,
		touch,
		connect: async (value) => {
			connect(value);
			await settle();
		},
		failSend: () => {
			deliver = false;
		},
	};
}

const field = (dial) => dial.output.feedback.at(-1);
const choice = (h, filter, index) => h.client.state.library[`${filter}_filter`].options[index];

test("filter dials choose bounded exact dropdown values locally, including All, Unknown and all statuses", async () => {
	const h = await harness();
	assert.equal(dialSettings({ control: "filter", filter: "search" }), undefined);
	h.mode.toggle("plus");
	h.mode.toggle("plus");
	for (const [filter, dial] of [
		["park", h.park],
		["status", h.status],
	]) {
		const options = h.client.state.library[`${filter}_filter`].options;
		for (let index = 1; index < options.length; index++) {
			const before = h.sent.length;
			await h.rotate(dial, 1);
			assert.equal(h.sent.length, before, "Rotation must never send a filter command");
			assert.equal(field(dial).value, options[index].label);
			assert.match(field(dial).status.value, /Preview/);
			assert.match(field(dial).detail, new RegExp(`^Active: ${options[index - 1].label}$`));
			await h.press(dial);
			assert.deepEqual(h.sent.at(-1).action, { name: "library.filter.set", filter, value: options[index].value });
			await h.reply();
			assert.match(field(dial).detail, new RegExp(`^Active: ${options[index - 1].label}$`), "ACK is not confirmation");
			await h.publish((state) => {
				state.library[`${filter}_filter`].value = options[index].value;
			});
			assert.equal(field(dial).detail, `Active: ${options[index].label}`);
			assert.match(field(dial).status.value, /Ready/);
		}
		await h.rotate(dial, 100);
		assert.equal(field(dial).value, options.at(-1).label);
		await h.rotate(dial, -100);
		assert.equal(field(dial).value, options[0].label);
		await h.rotate(dial, -1);
		assert.equal(field(dial).value, options[0].label);
		await h.press(dial);
		assert.deepEqual(h.sent.at(-1).action, { name: "library.filter.set", filter, value: null });
		await h.reply();
		await h.publish((state) => {
			state.library[`${filter}_filter`].value = null;
		});
		await h.rotate(dial, 2);
		assert.equal(field(dial).value, options[2].label, "Multiple ticks retain one option per notch");
		await h.touch(dial);
		assert.deepEqual(h.sent.at(-1).action, { name: "library.filter.set", filter, value: null });
		assert.equal(field(dial).value, options[0].label);
		await h.reply();
	}
});

test("filter feedback keeps long Unicode labels in text and never fabricates successful application", async () => {
	const h = await harness();
	const name = "Park <&\"'> 🎢 é / 東京 ".repeat(150);
	await h.publish((state) => {
		state.library.park_filter.options.push({ value: name, label: name });
	});
	await h.rotate(h.park, 100);
	assert.equal(field(h.park).value, name);
	assert.doesNotMatch(field(h.park).icon, /東京|&quot;|Park </);
	await h.press(h.park);
	assert.deepEqual(h.sent.at(-1).action, { name: "library.filter.set", filter: "park", value: name });
	assert.match(field(h.park).status.value, /Pending/);
	await h.reply("error");
	assert.match(field(h.park).status.value, /Failed/);
	assert.equal(field(h.park).detail, "Active: All parks");
	assert.equal(field(h.park).value, name);
	assert.equal(h.park.output.alerts, 1);
	h.failSend();
	const before = h.sent.length;
	await h.press(h.park);
	assert.equal(h.sent.length, before);
	assert.equal(h.park.output.alerts, 2);
	assert.equal(field(h.park).detail, "Active: All parks");
});

test("GUI and option changes discard only stale proposals, even with empty or single-entry results", async () => {
	const h = await harness();
	await h.rotate(h.park, 2);
	await h.rotate(h.status, 2);
	await h.publish((state) => {
		state.library.park_filter.value = "";
	});
	assert.equal(field(h.park).value, "Unknown park");
	assert.match(field(h.park).status.value, /Ready/);
	assert.equal(field(h.status).value, choice(h, "status", 2).label);
	assert.match(field(h.status).status.value, /Preview/);
	await h.publish((state) => {
		state.library.status_filter.options[2].label = "Updated label";
	});
	assert.equal(field(h.status).value, "All statuses");
	await h.rotate(h.park, 2);
	await h.publish((state) => {
		state.library.park_filter.options.splice(3, 1);
	});
	assert.equal(field(h.park).value, "Unknown park", "Removed option discards proposal");
	for (const count of [0, 1]) {
		await h.publish((state) => {
			state.library.count = count;
			state.library.selected = count ? { id: "single", index: 0, title: "Single" } : null;
		});
		await h.rotate(h.status, 1);
		await h.press(h.status);
		assert.deepEqual(h.sent.at(-1).action, { name: "library.filter.set", filter: "status", value: "imported" });
		await h.reply();
		await h.touch(h.status);
		await h.reply();
	}
	await h.publish((state) => {
		state.library.park_filter = { value: null, options: [] };
	});
	const before = h.sent.length;
	await h.rotate(h.park, 1);
	await h.press(h.park);
	await h.touch(h.park);
	assert.equal(h.sent.length, before);
	assert.equal(field(h.park).value, "—");
});

test("device proposals are independent and reset on page, target, recording, session and connection changes", async () => {
	const h = await harness();
	const other = surface("park", "other-plus");
	await h.dials.onWillAppear(other);
	await h.rotate(h.park, 2);
	await h.rotate(other, 1);
	await h.rotate(h.status, 1);
	assert.equal(field(other).value, "Unknown park");
	assert.equal(field(h.park).value, "Park A");
	await h.touch(h.park);
	await h.reply();
	assert.equal(field(h.status).value, "Imported", "Park touch preserves Status proposal");
	assert.equal(field(other).value, "Unknown park", "Touch preserves another device's proposal");
	await h.rotate(h.park, 2);
	await h.keys.onKeyDown(surface("reset"));
	await settle();
	assert.equal(h.sent.at(-1).action.name, "library.filter.reset");
	assert.equal(field(h.park).value, "All parks");
	assert.equal(field(h.status).value, "All statuses");
	await h.reply();
	await h.rotate(h.park, 2);
	h.dials.onWillDisappear(h.park);
	h.dials.onWillDisappear(h.status);
	await h.dials.onWillAppear(h.park);
	await h.dials.onWillAppear(h.status);
	assert.equal(field(h.park).value, "All parks");
	for (const change of [
		(state) => {
			state.target.window_id = "other-window";
		},
		(state) => {
			state.target.recording_id = "other-recording";
			state.target.generation++;
		},
		(state) => {
			state.session_id = "other-session";
		},
	]) {
		await h.rotate(h.park, 2);
		await h.rotate(h.status, 1);
		const before = h.sent.length;
		await h.publish(change);
		assert.equal(field(h.park).value, "All parks");
		assert.equal(field(h.status).value, "All statuses");
		assert.equal(h.sent.length, before);
	}
	await h.rotate(h.park, 2);
	await h.press(h.park);
	const before = h.sent.length;
	await h.connect(false);
	assert.equal(field(h.park).value, "—");
	await h.connect(true);
	await h.publish();
	assert.equal(field(h.park).value, "All parks");
	assert.equal(field(other).value, "All parks");
	assert.equal(h.sent.length, before, "Reconnect must not replay a proposal or command");
	h.dials.onWillDisappear(h.park);
	await h.press(h.park);
	assert.equal(h.sent.length, before, "Late events from a vanished page cannot send commands");
});

test("focus, dialog, background and command locks prevent filter changes and never confirm touch resets", async () => {
	const h = await harness();
	await h.publish((state) => {
		state.library.park_filter.value = "Park A";
	});
	for (const reason of ["input.focused", "dialog.open", "application.background", "application.busy"]) {
		await h.rotate(h.park, 1);
		await h.rotate(h.status, 1);
		await h.publish((state) => {
			state.availability = { available: false, reason };
		});
		const before = h.sent.length;
		await h.rotate(h.park, 1);
		await h.press(h.park);
		await h.touch(h.park);
		assert.equal(h.sent.length, before);
		assert.equal(field(h.park).detail, "Active: Park A");
		assert.equal(field(h.park).value, "Park A", "Touch discards the proposal even while blocked");
		await h.keys.onKeyDown(surface("reset"));
		await settle();
		assert.equal(h.sent.length, before);
		assert.equal(field(h.status).value, "All statuses");
		await h.publish((state) => {
			state.availability = { available: true };
		});
	}
	await h.publish((state) => {
		state.controls["library.filter.set"] = { available: false, reason: "operation.unsupported" };
	});
	const before = h.sent.length;
	await h.rotate(h.status, 1);
	await h.press(h.status);
	await h.touch(h.status);
	assert.equal(h.sent.length, before);
	await h.connect(false);
	await h.rotate(h.park, 3);
	await h.press(h.park);
	await h.touch(h.park);
	assert.equal(h.sent.length, before);
});

test("stale-target failure discards proposals and does not replay into the replacement Explorer", async () => {
	const h = await harness();
	await h.rotate(h.park, 2);
	await h.rotate(h.status, 2);
	await h.press(h.park);
	await h.reply("error", "target.stale");
	assert.equal(field(h.park).value, "—");
	assert.equal(field(h.status).value, "—");
	await h.publish((state) => {
		state.target.window_id = "replacement-window";
	});
	assert.equal(field(h.park).value, "All parks");
	assert.equal(field(h.status).value, "All statuses");
	assert.equal(h.sent.length, 1);
	await h.press(h.park);
	assert.equal(h.sent.at(-1).target.window_id, "replacement-window");
	assert.deepEqual(h.sent.at(-1).action, { name: "library.filter.set", filter: "park", value: null });
});
