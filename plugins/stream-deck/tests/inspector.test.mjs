import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";

import { pluginOutput } from "../scripts/artifact-path.mjs";

/**
 * Load the built inspector against simulated DOM elements and a connecting socket.
 * @param {object} settings Saved key settings restored when the inspector opens.
 * @returns {Promise<object>} Inspector elements, socket and simulated open helper.
 */
async function inspector(settings = { operation: "curve.set", curve: "combined" }) {
	const elements = new Map();
	elements.set("settings-status", { hidden: true, textContent: "" });
	const html = await readFile(path.join(pluginOutput, "ui/control.html"), "utf8");
	const [, helpUrl] = html.match(/id="setup-help" href="([^"]+)"/);
	elements.set("setup-help", {
		href: helpUrl,
		listeners: {},
		addEventListener(event, callback) {
			this.listeners[event] = callback;
		},
	});
	for (const id of ["operation", "direction", "steps", "curve", "marker", "boundary"]) {
		const markup = html.match(new RegExp(`id="${id}"[^>]*>([\\s\\S]*?)</select>`))[1];
		const element = {
			options: [...markup.matchAll(/<option value="([^"]+)"/g)].map(([, value]) => ({ value })),
			listeners: {},
			add(option) {
				this.options.push(option);
				this.value ||= option.value;
			},
			addEventListener(event, callback) {
				this.listeners[event] = callback;
			},
		};
		let selected = element.options[0]?.value ?? "";
		Object.defineProperty(element, "value", {
			get: () => selected,
			set: (value) => {
				selected = element.options.some((option) => option.value === value) ? value : "";
			},
		});
		elements.set(id, element);
		elements.set(`${id}-row`, { hidden: true });
	}
	const sockets = [];
	/**
	 *
	 */
	class Socket {
		/**
		 *
		 */
		static OPEN = 1;
		/**
		 *
		 * @param {string} url WebSocket endpoint requested by the inspector.
		 */
		constructor(url) {
			this.url = url;
			this.readyState = 0;
			this.listeners = {};
			this.messages = [];
			sockets.push(this);
		}
		/**
		 *
		 * @param {string} event Socket event name to deliver from the test.
		 * @param {Function} callback Callback invoked when the test emits the event.
		 */
		addEventListener(event, callback) {
			this.listeners[event] = callback;
		}
		/**
		 *
		 * @param {string} message Serialized inspector message sent to the native host.
		 */
		send(message) {
			this.messages.push(JSON.parse(message));
		}
	}
	const window = {};
	const code = await readFile(path.join(pluginOutput, "ui/control.js"), "utf8");
	vm.runInNewContext(code, {
		window,
		WebSocket: Socket,
		Option: class {
			/**
			 * Represent a native select option in the inspector test.
			 * @param {string} text Label shown for the option.
			 * @param {string} value Stored settings value represented by the option.
			 */
			constructor(text, value) {
				this.text = text;
				this.value = value;
			}
		},
		document: {
			getElementById: (id) => elements.get(id),
			querySelectorAll: () =>
				["operation", "direction", "steps", "curve", "marker", "boundary"].map((id) => elements.get(id)),
		},
	});
	window.connectElgatoStreamDeckSocket(
		"1234",
		"inspector-id",
		"registerPropertyInspector",
		"{}",
		JSON.stringify({ context: "key-context", payload: { settings } }),
	);
	const socket = sockets[0];
	return {
		elements,
		socket,
		status: elements.get("settings-status"),
		open() {
			socket.readyState = Socket.OPEN;
			socket.listeners.open();
		},
	};
}

test("the built inspector restores settings and automatically saves typed choices for the correct action", async () => {
	const { elements, socket, status, open } = await inspector();
	assert.equal(socket.url, "ws://127.0.0.1:1234");
	open();
	assert.deepEqual(socket.messages[0], { event: "registerPropertyInspector", uuid: "inspector-id" });
	assert.equal(status.hidden, true);
	assert.equal(elements.get("curve").value, "combined");
	assert.equal(elements.get("curve-row").hidden, false);
	elements.get("operation").value = "marker.preview";
	elements.get("marker").value = "end";
	elements.get("steps").value = "-10";
	elements.get("operation").listeners.change();
	const message = socket.messages.at(-1);
	assert.equal(message.event, "setSettings");
	assert.equal(message.context, "key-context");
	assert.equal(message.payload.operation, "marker.preview");
	assert.equal(message.payload.steps, -10);
	assert.equal(message.payload.marker, "end");
	assert.equal(elements.get("curve-row").hidden, true);
	assert.equal(elements.get("marker-row").hidden, false);
	assert.equal(elements.get("steps-row").hidden, false);
	assert.equal(status.hidden, true);
	assert.equal(socket.messages.length, 2, "A change must send exactly one automatic settings update");
});

test("setup help opens the existing user guide through the native URL command without navigating the inspector", async () => {
	const { elements, socket, open } = await inspector();
	const help = elements.get("setup-help");
	let prevented = 0;
	const click = () =>
		help.listeners.click({
			preventDefault() {
				prevented++;
			},
		});
	click();
	assert.equal(socket.messages.length, 0, "Help must not send on a connecting socket");
	open();
	click();
	assert.deepEqual(socket.messages.at(-1), {
		event: "openUrl",
		payload: {
			url: "https://github.com/rudnerbjoern/ride-forces-analyzer/blob/main/docs/user/STREAM_DECK.md",
		},
	});
	assert.equal(socket.messages.length, 2, "Help must not save or change the action settings");
	socket.readyState = 3;
	socket.listeners.close();
	click();
	assert.equal(socket.messages.length, 2, "Help must not send on a closed socket");
	assert.equal(prevented, 3, "Link activation must always prevent navigation within the inspector");
});

test("invalid restored settings show defaults and inline validation without silently overwriting saved values", async () => {
	for (const settings of [
		{ operation: "unknown" },
		{ steps: 0 },
		{ curve: "unknown" },
	]) {
		const { elements, socket, status, open } = await inspector(settings);
		open();
		assert.equal(status.hidden, false);
		assert.match(status.textContent, /Saved settings are invalid/);
		assert.match(status.textContent, /Defaults are shown/);
		assert.equal(elements.get("operation").value, "playback.toggle");
		assert.equal(socket.messages.length, 1, "Displaying defaults must never save them automatically");
		elements.get("operation").value = "view.reset";
		elements.get("operation").listeners.change();
		assert.equal(socket.messages.at(-1).payload.operation, "view.reset");
		assert.equal(status.hidden, true);
		socket.listeners.message({ data: JSON.stringify({ event: "didReceiveSettings", payload: { settings } }) });
		assert.equal(status.hidden, false);
		assert.match(status.textContent, /Saved settings are invalid/);
		socket.listeners.message({ data: JSON.stringify({ event: "didReceiveSettings", payload: { settings: {} } }) });
		assert.equal(status.hidden, true);
		assert.equal(socket.messages.length, 2);
	}
});

test("every admitted sample-step choice restores and autosaves through native select options", async () => {
	for (const steps of [-20, -10, -1, 1, 10, 20]) {
		const { elements, socket, status, open } = await inspector({ operation: "position.step", steps });
		open();
		assert.equal(elements.get("steps").value, String(steps));
		elements.get("marker").listeners.change();
		assert.equal(socket.messages.at(-1).event, "setSettings");
		assert.equal(socket.messages.at(-1).payload.steps, steps);
		assert.equal(status.hidden, true);
	}
});

test("changes made before connection remain visibly unsaved until another selection sends them", async () => {
	const { elements, socket, status, open } = await inspector();
	assert.equal(status.hidden, false);
	assert.match(status.textContent, /Settings connection unavailable/);
	elements.get("operation").value = "view.reset";
	elements.get("operation").listeners.change();
	assert.equal(socket.messages.length, 0);
	assert.match(status.textContent, /Changes cannot be saved/);
	open();
	assert.equal(socket.messages.length, 1, "Opening the connection must not silently replay an unsaved change");
	assert.equal(status.hidden, false);
	assert.match(status.textContent, /Changes were not saved/);
	elements.get("operation").value = "view.selection";
	elements.get("operation").listeners.change();
	assert.equal(socket.messages.at(-1).payload.operation, "view.selection");
	assert.equal(status.hidden, true);
});

test("closed or failed settings connections explain why changes cannot be saved", async () => {
	for (const event of ["close", "error"]) {
		const { elements, socket, status, open } = await inspector();
		open();
		if (event === "close") socket.readyState = 3;
		socket.listeners[event]();
		assert.equal(status.hidden, false);
		assert.match(status.textContent, /Settings connection unavailable/);
		assert.match(status.textContent, /Reopen this inspector/);
		elements.get("operation").value = "view.reset";
		elements.get("operation").listeners.change();
		assert.equal(socket.messages.length, 1, "An unavailable connection must not receive settings changes");
		assert.equal(status.hidden, false);
	}
});

test("a failed settings send keeps the inline unsaved message", async (t) => {
	const { elements, socket, status, open } = await inspector();
	open();
	t.mock.method(socket, "send", () => {
		throw new Error("Socket closed during send");
	});
	elements.get("operation").value = "view.reset";
	assert.doesNotThrow(() => elements.get("operation").listeners.change());
	assert.equal(status.hidden, false);
	assert.match(status.textContent, /Changes were not saved/);
});
