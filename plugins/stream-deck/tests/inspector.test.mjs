import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import path from "node:path";
import { pluginOutput } from "../scripts/artifact-path.mjs";

test("the built inspector restores settings and saves typed choices for the correct action", async () => {
  const elements = new Map();
  for (const id of ["operation", "direction", "steps", "curve", "marker"]) {
    elements.set(id, { value: "", options: [], listeners: {},
      add(option) { this.options.push(option); this.value ||= option.value; },
      addEventListener(event, callback) { this.listeners[event] = callback; } });
    elements.set(`${id}-row`, { hidden: true });
  }
  const sockets = [];
  class Socket {
    static OPEN = 1;
    constructor(url) { this.url = url; this.readyState = 1; this.listeners = {}; this.messages = []; sockets.push(this); }
    addEventListener(event, callback) { this.listeners[event] = callback; }
    send(message) { this.messages.push(JSON.parse(message)); }
  }
  const window = {};
  const code = await readFile(path.join(pluginOutput, "ui/control.js"), "utf8");
  vm.runInNewContext(code, { window, WebSocket: Socket,
    Option: class { constructor(text, value) { this.text = text; this.value = value; } },
    document: { getElementById: id => elements.get(id),
      querySelectorAll: () => ["operation", "direction", "steps", "curve", "marker"].map(id => elements.get(id)) } });
  window.connectElgatoStreamDeckSocket("1234", "inspector-id", "registerPropertyInspector", "{}",
    JSON.stringify({ context: "key-context", payload: { settings: { operation: "curve.set", curve: "combined" } } }));
  const socket = sockets[0];
  assert.equal(socket.url, "ws://127.0.0.1:1234");
  socket.listeners.open();
  assert.deepEqual(socket.messages[0], { event: "registerPropertyInspector", uuid: "inspector-id" });
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
});
