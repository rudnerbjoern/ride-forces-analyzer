import streamDeck from "@elgato/streamdeck";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { setImmediate } from "node:timers/promises";
import { fileURLToPath } from "node:url";

import { ControlAction } from "../dist/action.js";
import { ControlClient } from "../dist/client.js";
import { logFailure } from "../dist/diagnostics.js";
import { AnalyzerTransport } from "../dist/transport.js";

const realTimeout = setTimeout;
const token = "d".repeat(64);
const privateData = "private-recording-payload-GPS";
const fixture = JSON.parse(
	await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
).messages[0];

/**
 * Capture actual SDK logger calls without writing unit-test logs to the repository root.
 * @param {object} t Node test context restoring logger methods after the test.
 * @returns {object[]} Log levels and structured arguments captured by the SDK mocks.
 */
function capture(t) {
	const logs = [];
	for (const level of ["info", "warn", "error"])
		t.mock.method(streamDeck.logger, level, (...args) => logs.push({ level, args }));
	return logs;
}

/**
 * Wait for real filesystem IO while retry and handshake timers use virtual time.
 * @param {Function} condition Expected asynchronous transport outcome.
 */
async function waitFor(condition) {
	const deadline = Date.now() + 3000;
	while (!condition()) {
		assert.ok(Date.now() < deadline, "Diagnostic transport outcome timed out");
		await new Promise((resolve) => realTimeout(resolve, 5));
	}
}

/**
 * Prepare one discovery file, simulated socket host and deterministic retry clock.
 * @param {object} t Node test context owning cleanup and virtual timers.
 * @returns {Promise<object>} Transport, sockets, log capture and retry helper.
 */
async function transport(t) {
	const logs = capture(t);
	const directory = await mkdtemp(fileURLToPath(new URL("../../../.tmp/stream-deck-diagnostics-", import.meta.url)));
	const filename = path.join(directory, "endpoint.json");
	const sockets = [];
	const original = globalThis.WebSocket;
	/** Simulate socket events without network traffic or real retry waits. */
	class Socket {
		/** Native ready-state value accepted by the transport. */
		static OPEN = 1;
		/** Register one disconnected simulated connection attempt. */
		constructor() {
			this.readyState = 0;
			this.listeners = {};
			this.messages = [];
			sockets.push(this);
		}
		/**
		 * Store a native event subscription.
		 * @param {string} event Event name.
		 * @param {Function} callback Callback invoked by the test.
		 */
		addEventListener(event, callback) {
			this.listeners[event] = callback;
		}
		/**
		 * Capture outgoing data separately from diagnostic logs.
		 * @param {string} value Outgoing message text.
		 */
		send(value) {
			this.messages.push(value);
		}
		/** Complete the socket opening stage. */
		open() {
			this.readyState = 1;
			this.listeners.open();
		}
		/**
		 * Deliver a server message.
		 * @param {unknown} data Server-controlled message data.
		 */
		message(data) {
			this.listeners.message({ data });
		}
		/**
		 * Close with deliberately private server-provided reason text.
		 * @param {number} code Native close status code.
		 */
		close(code = 1000) {
			if (this.readyState === 3) return;
			this.readyState = 3;
			this.listeners.close({ code, reason: token + privateData });
		}
	}
	globalThis.WebSocket = Socket;
	t.mock.timers.enable({ apis: ["setTimeout"] });
	const client = new AnalyzerTransport(filename, () => {});
	t.after(async () => {
		client.stop();
		globalThis.WebSocket = original;
		await rm(directory, { recursive: true, force: true });
	});
	return {
		client,
		logs,
		sockets,
		filename,
		async discover() {
			await writeFile(filename, JSON.stringify({ version: 1, port: 1234, token }));
		},
		async retry() {
			const next = sockets.length + 1;
			t.mock.timers.tick(1000);
			await waitFor(() => sockets.length === next);
			return sockets.at(-1);
		},
	};
}

test("SDK failures include safe error categories/codes and exclude messages, stacks and custom properties", (t) => {
	const logs = capture(t);
	const failure = Object.assign(new TypeError(token + privateData), { code: "ECONNRESET", payload: privateData });
	logFailure("Native request failed", failure);
	assert.deepEqual(logs[0], {
		level: "error",
		args: ["Native request failed", { type: "TypeError", code: "ECONNRESET" }],
	});
	logFailure("Native request failed", { name: token, code: privateData, payload: privateData }, "warn");
	assert.deepEqual(logs[1], { level: "warn", args: ["Native request failed", { type: "UnknownError" }] });
	assert.ok(!JSON.stringify(logs).includes(token));
	assert.ok(!JSON.stringify(logs).includes(privateData));
});

test("discovery diagnostics report transitions once while repeated normal offline retries stay quiet", async (t) => {
	const h = await transport(t);
	h.client.start();
	await waitFor(() => h.logs.length === 1);
	assert.equal(h.logs[0].args[1].reason, "discovery.missing");
	for (let index = 0; index < 2; index++) {
		t.mock.timers.tick(1000);
		await new Promise((resolve) => realTimeout(resolve, 15));
	}
	assert.equal(h.logs.length, 1);
	await writeFile(h.filename, `{invalid:${token}${privateData}`);
	t.mock.timers.tick(1000);
	await waitFor(() => h.logs.length === 2);
	assert.equal(h.logs.at(-1).args[1].reason, "discovery.invalid");
	t.mock.timers.tick(1000);
	await new Promise((resolve) => realTimeout(resolve, 15));
	assert.equal(h.logs.length, 2);
	assert.ok(!JSON.stringify(h.logs).includes(token));
	assert.ok(!JSON.stringify(h.logs).includes(privateData));
});

test("authentication failures, timeout, recovery and command send failure log only safe reason transitions", async (t) => {
	const h = await transport(t);
	await h.discover();
	h.client.start();
	await waitFor(() => h.sockets.length === 1);
	let socket = h.sockets.at(-1);
	socket.open();
	socket.message(`invalid-${token}-${privateData}`);
	assert.equal(h.logs.at(-1).args[1].reason, "authentication.invalid");
	socket = await h.retry();
	socket.open();
	socket.message(JSON.stringify({ rejected: token + privateData }));
	assert.equal(h.logs.at(-1).args[1].reason, "authentication.rejected");
	const count = h.logs.length;
	socket = await h.retry();
	socket.open();
	socket.message(JSON.stringify({ rejected: token + privateData }));
	assert.equal(h.logs.length, count, "Repeated authentication rejection must not flood the SDK log");
	socket = await h.retry();
	socket.open();
	t.mock.timers.tick(5000);
	assert.equal(h.logs.at(-1).args[1].reason, "authentication.timeout");
	socket = await h.retry();
	socket.listeners.error({ message: token + privateData });
	assert.equal(h.logs.at(-1).args[1].reason, "connection.failed");
	socket = await h.retry();
	socket.send = () => {
		throw new Error(token + privateData);
	};
	socket.open();
	assert.equal(h.logs.at(-1).args[1].reason, "authentication.send.failed");
	socket = await h.retry();
	socket.open();
	socket.message('{"transport":"ready","version":1}');
	assert.equal(h.client.connected, true);
	assert.equal(h.logs.at(-1).args[1].reason, "connection.established");
	socket.message(new Uint8Array([1]));
	assert.equal(h.logs.at(-1).args[1].reason, "message.text.required");
	socket = await h.retry();
	socket.open();
	socket.message('{"transport":"ready","version":1}');
	socket.send = () => {
		throw new Error(token + privateData);
	};
	assert.equal(h.client.send(privateData), false);
	assert.equal(h.logs.at(-1).args[1].reason, "message.send.failed");
	assert.equal(h.client.connected, false);
	assert.ok(!JSON.stringify(h.logs).includes(token));
	assert.ok(!JSON.stringify(h.logs).includes(privateData));
});

test("invalid protocol messages and correlated failures use SDK diagnostics without logging source data", (t) => {
	const logs = capture(t);
	let receive;
	const sent = [];
	const client = new ControlClient((message) => {
		receive = (value) => message(typeof value === "string" ? value : JSON.stringify(value));
		return {
			start() {},
			stop() {},
			send(value) {
				sent.push(JSON.parse(value));
				return true;
			},
		};
	});
	receive(fixture);
	receive(token + privateData);
	receive(token + privateData);
	assert.equal(client.status, "incompatible");
	assert.equal(logs.length, 1);
	assert.equal(logs[0].args[1].reason, "server.message.invalid");
	receive({ ...fixture, sequence: fixture.sequence + 1 });
	assert.equal(client.send("key", { name: "playback.toggle" }), true);
	const response = {
		version: 3,
		type: "response",
		id: sent[0].id,
		target: sent[0].target,
		status: "error",
		code: "analysis.failed",
		reason: null,
	};
	receive(response);
	receive(response);
	assert.deepEqual(logs.at(-1).args, [
		"Analyzer command failed",
		{ command: "playback.toggle", code: "analysis.failed", reason: null },
	]);
	assert.equal(logs.length, 2);
	receive(token + privateData);
	assert.equal(logs.length, 3, "Recovery allows a new protocol transition to be diagnosed");
	assert.ok(!JSON.stringify(logs).includes(token));
	assert.ok(!JSON.stringify(logs).includes(privateData));
});

test("deferred rendering failures reach the SDK logger without rendering or recording payloads", async (t) => {
	const logs = capture(t);
	t.mock.timers.enable({ apis: ["Date", "setTimeout"], now: 10000 });
	let receive;
	const client = new ControlClient((message) => {
		receive = (value) => message(JSON.stringify(value));
		return {
			start() {},
			stop() {},
			send() {
				return true;
			},
		};
	});
	receive(fixture);
	const action = new ControlAction(client);
	const key = { id: "key", isKey: () => true, async setState() {}, async setImage() {}, async setTitle() {} };
	await action.onWillAppear({ action: key, payload: { settings: { operation: "position.step" } } });
	key.setTitle = async () => {
		throw new Error(token + privateData);
	};
	const state = structuredClone(fixture);
	state.sequence++;
	state.playback.position.label = "00:02.00";
	receive(state);
	t.mock.timers.tick(1000);
	await setImmediate();
	assert.equal(logs.at(-1).level, "error");
	assert.deepEqual(logs.at(-1).args, ["Stream Deck feedback failed", { type: "Error" }]);
	assert.ok(!JSON.stringify(logs).includes(token));
	assert.ok(!JSON.stringify(logs).includes(privateData));
});
