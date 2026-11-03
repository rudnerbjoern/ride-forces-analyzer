import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { ControlClient } from "../dist/client.js";
import { controlSettings, CONTROL_LABELS, requestedAction } from "../dist/controls.js";
import { decodeServerMessage } from "../dist/decoder.js";
import { keyFeedback } from "../dist/feedback.js";

const examples = JSON.parse(await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"));
const state = () => structuredClone(examples.messages[0]);

function harness() {
  let receive, connect;
  const sent = [];
  const client = new ControlClient((message, connection) => {
    receive = value => message(typeof value === "string" ? value : JSON.stringify(value));
    connect = connection;
    return { start() {}, stop() { connection(false); }, send(value) { sent.push(JSON.parse(value)); return true; } };
  });
  return { client, sent, receive, connect };
}

test("runtime decoding matches shared Python messages and rejects incompatible feedback", () => {
  for (const message of examples.messages) assert.deepEqual(decodeServerMessage(JSON.stringify(message)), message);
  for (const change of [
    { version: 99 }, { version: true }, { unexpected: true }, { sequence: -1 },
    { availability: { available: 1 } }, { controls: { unknown: { available: true } } },
    { playback: { ...state().playback, speed: 3 } },
    { view: { ...state().view, smoothing_window: 2 } },
    { markers: [{ ...state().markers[1], status: "pending", request_id: null }] },
  ]) assert.equal(decodeServerMessage(JSON.stringify({ ...state(), ...change })), undefined);
  assert.equal(decodeServerMessage("not JSON"), undefined);
  assert.equal(decodeServerMessage(" ".repeat(65537)), undefined);
});

test("all agreed operations are configurable and unavailable argument choices stay blocked", () => {
  assert.deepEqual(Object.keys(CONTROL_LABELS).sort(), [...new Set(examples.actions.map(action => action.name))].sort());
  for (const action of examples.actions) {
    const { name, enabled: _enabled, ...arguments_ } = action;
    const settings = controlSettings({ operation: name, ...arguments_ });
    assert.ok(settings);
    const requested = requestedAction(settings, state());
    if (name === "marker.discard") assert.equal(requested, undefined);
    else assert.deepEqual(requested, action);
  }
  assert.equal(controlSettings({ operation: "unknown" }), undefined);
  assert.equal(controlSettings({ steps: true }), undefined);
  assert.equal(controlSettings({ curve: "invalid" }), undefined);
  assert.equal(requestedAction(controlSettings({}), undefined), undefined);
  assert.equal(requestedAction(controlSettings({}), examples.messages[1]), undefined);
});

test("toggle images and key states follow confirmation, never key presses or acknowledgements", () => {
  const { client, sent, receive, connect } = harness();
  const settings = controlSettings({ operation: "curve.set", curve: "combined" });
  assert.equal(client.send("key", { name: "playback.toggle" }), false);
  connect(true);
  assert.equal(keyFeedback(client, "key", settings).state, 0);
  receive(state());
  const request = requestedAction(settings, client.state);
  assert.equal(client.send("key", request), true);
  assert.equal(sent[0].target.window_id, state().target.window_id);
  assert.deepEqual(sent[0].action, { name: "curve.set", curve: "combined", enabled: true });
  assert.equal(client.send("key", request), false);
  assert.equal(keyFeedback(client, "key", settings).state, 0);
  assert.match(keyFeedback(client, "key", settings).title, /Pending/);
  receive({ version: 2, type: "response", id: sent[0].id, target: sent[0].target, status: "ok" });
  assert.equal(keyFeedback(client, "key", settings).state, 0);
  const confirmed = state();
  confirmed.sequence++;
  confirmed.curves[3].active = true;
  receive(confirmed);
  assert.equal(keyFeedback(client, "key", settings).state, 1);
  receive(state());
  assert.equal(keyFeedback(client, "key", settings).state, 1);
});

test("restart, unavailable targets and incompatible messages clear actionable state without replay", () => {
  const { client, sent, receive, connect } = harness();
  connect(true); receive(state());
  client.send("key", { name: "playback.toggle" });
  connect(false);
  assert.equal(client.pending("key"), false);
  assert.equal(client.state, undefined);
  assert.match(keyFeedback(client, "key", controlSettings({})).title, /Offline/);
  connect(true);
  assert.equal(client.send("key", { name: "playback.toggle" }), false);
  receive({ ...state(), session_id: "restarted", sequence: 0 });
  assert.equal(client.status, "connected");
  assert.equal(sent.length, 1);
  receive(examples.messages[1]);
  assert.equal(client.send("key", { name: "playback.toggle" }), false);
  receive({ ...state(), version: 99 });
  assert.equal(client.status, "incompatible");
  assert.equal(client.state, undefined);
  assert.equal(client.send("key", { name: "playback.toggle" }), false);
  client.stop();
  assert.equal(client.status, "disconnected");
});

test("pending and failed marker adoption remain distinct from the last applied value", () => {
  const { client, sent, receive, connect } = harness();
  connect(true); receive(state());
  const settings = controlSettings({ operation: "marker.apply", marker: "gravity" });
  client.send("key", requestedAction(settings, client.state));
  receive({ version: 2, type: "response", id: sent[0].id, target: sent[0].target, status: "pending" });
  assert.equal(client.pending("key"), true);
  assert.equal(client.state.markers[1].applied.sample, 50);
  assert.match(keyFeedback(client, "key", settings).title, /Pending/);
  receive({ version: 2, type: "response", id: sent[0].id, target: sent[0].target,
    status: "error", code: "analysis_failed", reason: null });
  assert.equal(client.pending("key"), false);
  assert.equal(client.state.markers[1].applied.sample, 50);
  assert.match(keyFeedback(client, "key", settings).title, /Failed/);
  const blocked = state();
  blocked.sequence++;
  blocked.availability = { available: false, reason: "input_focus" };
  receive(blocked);
  assert.equal(client.send("other", { name: "playback.toggle" }), false);
});
