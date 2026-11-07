import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { setImmediate as settle } from "node:timers/promises";

import { ControlClient } from "../dist/client.js";
import { ControlAction } from "../dist/action.js";
import { DialControlAction } from "../dist/dial-action.js";
import { StepModeAction } from "../dist/mode-action.js";
import { InfoBarAction } from "../dist/infobar-action.js";
import { dialBinding, dialSettings, StepMode } from "../dist/device-controls.js";

const examples = JSON.parse(await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"));

function harness() {
  let message, connection;
  const sent = [];
  const client = new ControlClient((receive, connect) => {
    message = receive; connection = connect;
    return { start() {}, stop() { connect(false); }, send(value) { sent.push(JSON.parse(value)); return true; } };
  });
  const mode = new StepMode();
  const dials = new DialControlAction(client, mode);
  const modes = new StepModeAction(mode);
  const bars = new InfoBarAction(client);
  const keys = new ControlAction(client);
  let state = structuredClone(examples.messages[0]);
  const receive = value => message(JSON.stringify(value));
  const publish = update => { state = { ...state, ...update, sequence: state.sequence + 1 }; receive(state); };
  const acknowledge = () => {
    for (const command of sent) receive({ version: 4, type: "response", id: command.id, target: command.target, status: "ok" });
  };
  connection(true); receive(state);
  return { client, mode, dials, modes, bars, keys, sent, receive, publish, acknowledge, disconnect: () => connection(false) };
}

function surface(id, settings, kind = "dial", device = "plus") {
  const output = { feedback: [], layouts: [], titles: [], states: [], images: [], alerts: 0 };
  const action = { id, device: { id: device, type: device === "plus" ? 7 : 9 },
    isDial: () => kind === "dial", isKey: () => kind === "key", isNeoInfobar: () => kind === "bar",
    async setFeedback(value) { output.feedback.push(value); }, async setFeedbackLayout(value) { output.layouts.push(value); },
    async setTriggerDescription() {}, async setImage(value) { output.images.push(value); }, async setTitle(value) { output.titles.push(value); },
    async setState(value) { output.states.push(value); }, async showAlert() { output.alerts++; } };
  return { action, payload: { settings }, output };
}

test("every dial gesture maps to its existing command and shared sample size", () => {
  for (const size of [1, 10, 20]) for (const direction of [-1, 1]) {
    const steps = size * direction;
    const cases = [
      [{ control: "library" }, { operation: "library.move", direction }, { operation: "library.open" }, undefined],
      [{ control: "position" }, { operation: "position.step", steps }, { operation: "playback.toggle" }, undefined],
      [{ control: "speed" }, { operation: "playback.speed.step", direction }, { operation: "playback.speed.reset" }, undefined],
      [{ control: "view" }, { operation: "view.zoom", direction }, { operation: "view.reset" }, undefined],
      [{ control: "smoothing" }, { operation: "smoothing.step", direction }, { operation: "smoothing.reset" }, undefined],
      [{ control: "zoom_selection" }, undefined, { operation: "view.selection" }, undefined],
      [{ control: "combined" }, undefined, { operation: "curve.set", curve: "combined" }, undefined],
      [{ control: "playback" }, undefined, { operation: "playback.toggle" }, undefined],
      ...["start", "end"].map(boundary => [{ control: "selection", boundary }, { operation: "selection.step", boundary, steps }, undefined, undefined]),
      ...["start", "gravity", "incline", "end"].map(marker => [{ control: "marker", marker },
        { operation: "marker.preview", marker, steps }, { operation: "marker.apply", marker }, { operation: "marker.discard", marker }]),
    ];
    for (const [settings, ...expected] of cases) {
      assert.deepEqual(dialSettings(settings), settings);
      for (const [index, gesture] of ["rotate", "press", "touch"].entries()) {
        assert.deepEqual(dialBinding(settings, gesture, direction, size), expected[index]);
      }
    }
  }
  assert.equal(dialSettings({ control: "unknown" }), undefined);
});

test("press-only dials use press availability, confirmed values and silent unused gestures", async () => {
  for (const [control, command, initial] of [
    ["zoom_selection", { name: "view.selection" }, "#40–100"],
    ["combined", { name: "curve.set", curve: "combined", enabled: true }, "Off"],
    ["playback", { name: "playback.toggle" }, "Paused"],
  ]) {
    const h = harness();
    // Zoom rotation availability is irrelevant to these push functions.
    h.publish({ controls: { ...h.client.state.controls, "view.zoom": { available: false, reason: "input_focus" } } });
    const dial = surface(control, { control });
    await h.dials.onWillAppear(dial);
    assert.equal(dial.output.feedback.at(-1).value, initial);
    assert.equal(dial.output.feedback.at(-1).status, "PRESS ONLY");
    for (const ticks of [-3, 3]) await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks } });
    await h.dials.onTouchTap(dial);
    assert.equal(h.sent.length, 0);
    assert.equal(dial.output.alerts, 0);
    await h.dials.onDialDown(dial);
    assert.deepEqual(h.sent.at(-1).action, command);
    await settle();
    assert.equal(dial.output.feedback.at(-1).value, initial, "Sending must not change a confirmed value");
    h.acknowledge();
    const confirmed = structuredClone(h.client.state);
    if (control === "zoom_selection") confirmed.selection.end.sample = 120;
    if (control === "combined") confirmed.curves.find(curve => curve.curve === "combined").active = true;
    if (control === "playback") confirmed.playback.playing = true;
    h.publish(confirmed);
    await settle();
    assert.equal(dial.output.feedback.at(-1).value, control === "zoom_selection" ? "#40–120" : control === "combined" ? "On" : "Playing");
    const blocked = structuredClone(h.client.state);
    if (control === "combined") blocked.curves.find(curve => curve.curve === "combined").availability = { available: false, reason: "input_focus" };
    else blocked.controls[command.name] = { available: false, reason: "input_focus" };
    h.publish(blocked);
    await settle();
    assert.match(dial.output.feedback.at(-1).status, /Editing.*PRESS ONLY/);
    await h.dials.onDialDown(dial);
    assert.equal(h.sent.length, 1);
    assert.equal(dial.output.alerts, 1);
    h.disconnect();
    await settle();
    assert.equal(dial.output.feedback.at(-1).value, "—");
    assert.equal(dial.output.feedback.at(-1).status, "Offline · PRESS ONLY");
    await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks: 4 } });
    await h.dials.onTouchTap(dial);
    assert.equal(h.sent.length, 1);
    assert.equal(dial.output.alerts, 1, "Unused gestures remain silent while disconnected");
  }
});

test("Library dials retain every notch, never open while browsing and share confirmed key feedback", async () => {
  const h = harness();
  const dial = surface("library", { control: "library" });
  await h.dials.onWillAppear(dial);
  assert.equal(dial.output.feedback.at(-1).value, "Example ride");
  const icon = dial.output.feedback.at(-1).icon;
  assert.match(icon, /^data:image\/svg\+xml;base64,/);
  assert.match(Buffer.from(icon.split(",")[1], "base64").toString("utf8"), /^<svg /);
  assert.equal(dial.output.images.at(-1), icon);
  await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks: 3 } });
  assert.deepEqual(h.sent.map(value => value.action), Array(3).fill({ name: "library.move", direction: 1 }));
  h.acknowledge();
  h.publish({ library: { ...h.client.state.library, count: 2, selected: { id: "other", title: "Other ride", index: 1 } } });
  await settle();
  assert.equal(dial.output.feedback.at(-1).value, "Other ride");
  assert.match(dial.output.feedback.at(-1).detail, /2\/2/);
  h.mode.toggle("plus");
  h.mode.toggle("plus");
  await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks: -2 } });
  assert.deepEqual(h.sent.slice(-2).map(value => value.action), Array(2).fill({ name: "library.move", direction: -1 }));
  h.acknowledge();
  await h.dials.onDialDown(dial);
  assert.deepEqual(h.sent.at(-1).action, { name: "library.open" });
  assert.deepEqual(h.sent.at(-1).target, examples.messages[0].target);
  h.acknowledge();
  const previous = surface("previous", { operation: "library.move", direction: -1 }, "key", "neo");
  const open = surface("open", { operation: "library.open" }, "key", "neo");
  const import_ = surface("import", { operation: "library.import" }, "key", "neo");
  await h.keys.onKeyDown(previous);
  await h.keys.onKeyDown(previous);
  assert.deepEqual(h.sent.slice(-2).map(value => value.action), Array(2).fill({ name: "library.move", direction: -1 }));
  await h.keys.onKeyDown(open);
  await h.keys.onKeyDown(import_);
  assert.deepEqual(h.sent.slice(-2).map(value => value.action.name), ["library.open", "library.import"]);
  h.publish({ library: { ...h.client.state.library, count: 0, selected: null }, controls: { ...h.client.state.controls,
    "library.move": { available: false, reason: "empty_library" }, "library.open": { available: false, reason: "no_selection" } } });
  const count = h.sent.length;
  await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks: 1 } });
  await h.dials.onDialDown(dial);
  await h.keys.onKeyDown(open);
  assert.equal(h.sent.length, count);
  await settle();
  assert.equal(dial.output.feedback.at(-1).value, "Empty Library");
  assert.match(dial.output.feedback.at(-1).detail, /Open unavailable/);
});

test("Plus navigation uses fine/coarse samples per tick and existing reset/play commands", async () => {
  const h = harness();
  const position = surface("position", { control: "position" });
  const mode = surface("mode", {}, "key");
  await h.dials.onWillAppear(position);
  await h.modes.onWillAppear(mode);
  assert.match(mode.output.titles.at(-1), /Fine/);
  assert.match(mode.output.images.at(-1), /^data:image\/svg\+xml;base64,/);
  assert.doesNotMatch(Buffer.from(mode.output.images.at(-1).split(",")[1], "base64").toString("utf8"), /<circle cx="112"/);
  await h.dials.onDialRotate({ ...position, payload: { ...position.payload, ticks: 2 } });
  assert.deepEqual(h.sent.map(value => value.action.steps), [1, 1]);
  await h.modes.onKeyDown(mode);
  await h.dials.onDialRotate({ ...position, payload: { ...position.payload, ticks: -2 } });
  assert.deepEqual(h.sent.slice(-2).map(value => value.action.steps), [-10, -10]);
  assert.equal(h.mode.samples("another-plus"), 1);
  assert.equal(mode.output.titles.at(-1), "Medium\n10 samples");
  assert.match(Buffer.from(mode.output.images.at(-1).split(",")[1], "base64").toString("utf8"), /<title>medium: menu<\/title>/);
  assert.doesNotMatch(Buffer.from(mode.output.images.at(-1).split(",")[1], "base64").toString("utf8"), /<circle cx="112"/);
  await settle();
  assert.match(position.output.feedback.at(-1).status, /Pending/);
  assert.match(position.output.feedback.at(-1).status, /Medium/);
  h.acknowledge();
  await h.modes.onKeyDown(mode);
  assert.match(mode.output.titles.at(-1), /20 samples/);
  assert.equal(mode.output.titles.at(-1), "Coarse\n20 samples");
  assert.match(Buffer.from(mode.output.images.at(-1).split(",")[1], "base64").toString("utf8"), /<title>coarse: menu<\/title>/);
  assert.doesNotMatch(Buffer.from(mode.output.images.at(-1).split(",")[1], "base64").toString("utf8"), /<circle cx="112"/);
  assert.equal(mode.output.states.at(-1), 2);
  await h.dials.onDialRotate({ ...position, payload: { ...position.payload, ticks: 1 } });
  assert.equal(h.sent.at(-1).action.steps, 20);
  await settle();
  assert.match(position.output.feedback.at(-1).status, /20 samples/);
  await h.modes.onKeyDown(mode);
  assert.equal(h.mode.samples("plus"), 1);
  assert.match(mode.output.titles.at(-1), /Fine/);
  h.acknowledge();
  await h.dials.onDialDown(position);
  assert.deepEqual(h.sent.at(-1).action, { name: "playback.toggle" });
  h.acknowledge();
  for (const [control, step, reset] of [["view", "view.zoom", "view.reset"],
    ["smoothing", "smoothing.step", "smoothing.reset"], ["speed", "playback.speed.step", "playback.speed.reset"]]) {
    const dial = surface(control, { control });
    await h.dials.onWillAppear(dial);
    await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks: -2 } });
    assert.deepEqual(h.sent.slice(-2).map(value => value.action), Array(2).fill({ name: step, direction: -1 }));
    h.acknowledge();
    await h.dials.onDialDown(dial);
    assert.deepEqual(h.sent.at(-1).action, { name: reset });
    const count = h.sent.length;
    await h.dials.onTouchTap(dial);
    assert.equal(h.sent.length, count);
    h.acknowledge();
  }
  h.publish({ availability: { available: false, reason: "input_focus" } });
  const count = h.sent.length;
  await h.dials.onDialRotate({ ...position, payload: { ...position.payload, ticks: 1 } });
  assert.equal(h.sent.length, count);
  h.disconnect();
  await settle();
  assert.equal(position.output.feedback.at(-1).value, "—");
  assert.equal(position.output.feedback.at(-1).status, "Offline");
});

test("Plus marker rotation previews only its marker, press applies and touch discards with confirmed status", async () => {
  const h = harness();
  const dial = surface("gravity", { control: "marker", marker: "gravity" });
  await h.dials.onWillAppear(dial);
  await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks: -2 } });
  assert.deepEqual(h.sent.map(value => value.action), Array(2).fill({ name: "marker.preview", marker: "gravity", steps: -1 }));
  h.acknowledge();
  assert.match(dial.output.feedback.at(-1).detail, /Applied #50/);
  h.mode.toggle("plus"); h.mode.toggle("plus");
  await h.dials.onDialRotate({ ...dial, payload: { ...dial.payload, ticks: 1 } });
  assert.deepEqual(h.sent.at(-1).action, { name: "marker.preview", marker: "gravity", steps: 20 });
  h.acknowledge();
  h.dials.onWillDisappear(dial);
  await h.dials.onWillAppear(dial);
  assert.match(dial.output.feedback.at(-1).value, /#51/);
  await h.dials.onDialDown(dial);
  const apply = h.sent.at(-1);
  assert.deepEqual(apply.action, { name: "marker.apply", marker: "gravity" });
  h.receive({ version: 4, type: "response", id: apply.id, target: apply.target, status: "pending" });
  const markers = structuredClone(h.client.state.markers);
  markers[1] = { ...markers[1], status: "pending", request_id: apply.id };
  h.publish({ markers });
  await settle();
  assert.match(dial.output.feedback.at(-1).status, /Pending/);
  assert.doesNotMatch(dial.output.feedback.at(-1).status, /Pending · Pending/);
  assert.match(dial.output.feedback.at(-1).detail, /Applied #50/);
  h.receive({ version: 4, type: "response", id: apply.id, target: apply.target, status: "error", code: "analysis_failed", reason: null });
  markers[1] = { ...markers[1], status: "failed", error: "analysis_failed" };
  h.publish({ markers });
  await settle();
  assert.match(dial.output.feedback.at(-1).status, /Failed/);
  assert.doesNotMatch(dial.output.feedback.at(-1).status, /Failed · Failed/);
  assert.match(dial.output.feedback.at(-1).detail, /Applied #50/);
  await h.dials.onTouchTap(dial);
  assert.deepEqual(h.sent.at(-1).action, { name: "marker.discard", marker: "gravity" });
  h.acknowledge();
  markers[1] = { ...markers[1], status: "applied", preview: null, request_id: null, error: null };
  h.publish({ markers });
  await settle();
  assert.match(dial.output.feedback.at(-1).value, /#50/);
  const count = h.sent.length;
  h.publish({ target: { window_id: "another-window", recording_id: "another-ride", generation: 4 }, markers: [] });
  await settle();
  assert.equal(h.sent.length, count, "Target changes cannot replay or apply previews");
  assert.equal(dial.output.feedback.at(-1).value, "Unset");
  for (const marker of ["start", "incline", "end"]) {
    h.publish({ markers: structuredClone(examples.messages[0].markers) });
    const other = surface(marker, { control: "marker", marker });
    await h.dials.onDialRotate({ ...other, payload: { ...other.payload, ticks: 1 } });
    assert.equal(h.sent.at(-1).action.marker, marker);
  }
});

test("Neo InfoBar renders Library, playback, curves and marker application without receiving inputs", async () => {
  const h = harness();
  const bar = surface("info", { section: "library" }, "bar", "neo");
  await h.bars.onWillAppear(bar);
  assert.deepEqual(bar.output.layouts, ["layouts/neo.json"]);
  assert.equal(bar.output.feedback.at(-1).value, "Example ride");
  assert.match(bar.output.feedback.at(-1).status, /1\/2/);
  await h.bars.onDidReceiveSettings({ ...bar, payload: { settings: { section: "playback" } } });
  assert.match(bar.output.feedback.at(-1).value, /#50.*00:01.00/);
  assert.match(bar.output.feedback.at(-1).status, /Paused.*1×/);
  await h.bars.onDidReceiveSettings({ ...bar, payload: { settings: { section: "view" } } });
  assert.match(bar.output.feedback.at(-1).title, /curves/);
  await h.bars.onDidReceiveSettings({ ...bar, payload: { settings: { section: "markers", marker: "gravity" } } });
  assert.match(bar.output.feedback.at(-1).title, /Gravity.*Preview/);
  assert.match(bar.output.feedback.at(-1).value, /#51/);
  assert.match(bar.output.feedback.at(-1).status, /Applied #50/);
  const markers = structuredClone(h.client.state.markers);
  markers[1] = { ...markers[1], status: "pending", request_id: "pending-apply" };
  h.publish({ markers }); await settle();
  assert.match(bar.output.feedback.at(-1).title, /Pending/);
  assert.match(bar.output.feedback.at(-1).status, /Applied #50/);
  h.publish({ availability: { available: false, reason: "busy" } }); await settle();
  assert.match(bar.output.feedback.at(-1).title, /Pending/);
  h.publish({ availability: { available: true } }); await settle();
  markers[1] = { ...markers[1], status: "failed", error: "analysis_failed" };
  h.publish({ markers }); await settle();
  assert.match(bar.output.feedback.at(-1).title, /Failed/);
  h.publish({ availability: { available: false, reason: "dialog_open" } }); await settle();
  assert.match(bar.output.feedback.at(-1).title, /Failed/);
  markers[1] = { ...markers[1], status: "preview", error: null, request_id: null };
  h.publish({ markers }); await settle();
  assert.match(bar.output.feedback.at(-1).title, /Dialog open/);
  h.disconnect(); await settle();
  assert.equal(bar.output.feedback.at(-1).value, "—");
  assert.equal(bar.output.feedback.at(-1).status, "Offline");
  assert.equal(h.bars.onKeyDown, undefined);
  assert.equal(h.bars.onDialRotate, undefined);
  assert.equal(h.bars.onTouchTap, undefined);
  assert.equal(h.sent.length, 0);
  h.bars.onWillDisappear(bar);
  await h.bars.onWillAppear(bar);
  assert.equal(bar.output.layouts.length, 2, "Layout is set on every appearance");
});


test("selection dials step independent bounds with fine/coarse feedback and no marker commands", async () => {
  const h = harness();
  const start = surface("selection-start", { control: "selection", boundary: "start" });
  const end = surface("selection-end", { control: "selection", boundary: "end" });
  await h.dials.onWillAppear(start); await h.dials.onWillAppear(end);
  assert.match(start.output.feedback.at(-1).value, /#40/);
  assert.match(end.output.feedback.at(-1).value, /#100/);
  await h.dials.onDialRotate({ ...start, payload: { ...start.payload, ticks: 2 } });
  assert.deepEqual(h.sent.map(command => command.action), Array(2).fill({ name: "selection.step", boundary: "start", steps: 1 }));
  h.acknowledge(); h.mode.toggle("plus");
  await h.dials.onDialRotate({ ...end, payload: { ...end.payload, ticks: -1 } });
  assert.deepEqual(h.sent.at(-1).action, { name: "selection.step", boundary: "end", steps: -10 });
  const count = h.sent.length;
  await h.dials.onDialDown(start); await h.dials.onTouchTap(end);
  assert.equal(h.sent.length, count);
  assert.equal(start.output.alerts, 0);
  h.publish({ selection: { ...h.client.state.selection, start: { sample: 42, time_seconds: .84, label: "00:00.84" } } });
  await settle();
  assert.match(start.output.feedback.at(-1).value, /#42/);
  assert.match(start.output.feedback.at(-1).status, /Medium/);
  assert.match(end.output.feedback.at(-1).detail, /Start #42/);
  h.acknowledge(); h.mode.toggle("plus");
  await h.dials.onDialRotate({ ...start, payload: { ...start.payload, ticks: -1 } });
  assert.deepEqual(h.sent.at(-1).action, { name: "selection.step", boundary: "start", steps: -20 });
});
