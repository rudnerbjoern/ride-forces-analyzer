import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { actionIcon, keyFeedback, keyImage } from "../dist/feedback.js";
import { dialFeedback } from "../dist/device-feedback.js";

const snapshot = JSON.parse(await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8")).messages[0];
const client = () => ({ state: structuredClone(snapshot), status: "connected", pending: () => false, error: () => undefined });

test("function icons distinguish browsing, import/open, direction, zoom and marker commands", () => {
  const actions = [
    { operation: "library.move", direction: -1 }, { operation: "library.move", direction: 1 },
    { operation: "library.open" }, { operation: "library.open_new_window" }, { operation: "library.import" },
    ...[-10, -1, 1, 10].map(steps => ({ operation: "position.step", steps })),
    { operation: "view.zoom", direction: -1 }, { operation: "view.zoom", direction: 1 },
    { operation: "view.reset" }, { operation: "view.selection" },
    ...["start", "gravity", "incline", "end"].map(marker => ({ operation: "marker.preview", marker })),
    { operation: "marker.apply" }, { operation: "marker.discard" },
  ];
  const icons = actions.map(settings => keyImage(actionIcon(settings), "inactive"));
  assert.equal(new Set(icons).size, actions.length);
  const h = client();
  const before = keyFeedback(h, "play", { operation: "playback.toggle" });
  assert.match(before.image, /<title>playback: inactive<\/title>/);
  h.state.playback.playing = true;
  const playing = keyFeedback(h, "play", { operation: "playback.toggle" });
  assert.match(playing.image, /<title>pause: active<\/title>/);
  assert.equal(playing.state, 1);
});

test("state badges distinguish confirmed, preview, pending, failed, blocked and offline values", () => {
  const states = ["inactive", "active", "preview", "pending", "failed", "unavailable", "disconnected"];
  const images = states.map(status => keyImage("gravity", status));
  assert.equal(new Set(images).size, states.length);
  const h = client();
  const marker = h.state.markers[0];
  assert.match(keyFeedback(h, "apply", { operation: "marker.apply", marker: "start" }).title, /No preview/);
  marker.status = "preview";
  marker.preview = { sample: 51, time_seconds: 1.02, label: "00:01.02" };
  const settings = { operation: "marker.preview", marker: "start", steps: 1 };
  assert.equal(keyFeedback(h, "marker", settings).status, "preview");
  h.state.availability = { available: false, reason: "input_focus" };
  assert.equal(keyFeedback(h, "marker", settings).status, "unavailable");
  assert.match(keyFeedback(h, "marker", settings).title, /Editing/);
  h.status = "disconnected";
  assert.equal(keyFeedback(h, "marker", settings).state, 0);
  assert.doesNotMatch(keyFeedback(h, "marker", settings).title, /00:01.02/);
});

test("touch fields follow GUI snapshots and retain adopted marker values through preview and failure", () => {
  const h = client();
  let field = dialFeedback(h, "dial", { control: "position" }, 1);
  assert.match(field.value, /#50.*00:01.00/);
  assert.match(field.status, /Paused.*Fine.*1 sample/);
  h.state.playback = { ...h.state.playback, playing: true, speed: 2,
    position: { sample: 80, time_seconds: 1.6, label: "00:01.60" } };
  field = dialFeedback(h, "dial", { control: "position" }, 10);
  assert.match(field.value, /#80.*00:01.60/);
  assert.match(field.status, /Playing.*Medium.*10 samples/);
  assert.match(field.detail, /2×.*Press: pause/);
  h.state.view = { start_seconds: 2, end_seconds: 7.5, smoothing_window: 21 };
  assert.equal(dialFeedback(h, "dial", { control: "view" }, 1).status, "Span 5.50 s");
  assert.equal(dialFeedback(h, "dial", { control: "smoothing" }, 1).value, "21 samples");
  const marker = h.state.markers[1];
  const settings = { control: "marker", marker: "gravity" };
  for (const status of ["preview", "pending", "failed"]) {
    marker.status = status;
    marker.preview = { sample: 70, time_seconds: 1.4, label: "00:01.40" };
    marker.request_id = status === "preview" ? null : "apply";
    marker.error = status === "failed" ? "analysis_failed" : null;
    field = dialFeedback(h, "dial", settings, 1);
    assert.match(field.value, /#70/);
    assert.match(field.detail, /Applied #50/);
    assert.match(field.status, new RegExp(status, "i"));
    assert.doesNotMatch(field.status, /Applied/);
  }
  marker.status = "applied"; marker.applied = marker.preview; marker.preview = null;
  marker.request_id = null; marker.error = null;
  field = dialFeedback(h, "dial", settings, 1);
  assert.match(field.status, /Applied/);
  assert.match(field.detail, /Applied #70/);
});

test("touch fields report blocking reasons and clear cached values when disconnected", () => {
  const h = client();
  const settings = { control: "position" };
  for (const [reason, label] of [["background", "Background"], ["dialog_open", "Dialog open"], ["input_focus", "Editing"]]) {
    h.state.availability = { available: false, reason };
    const field = dialFeedback(h, "dial", settings, 1);
    assert.match(field.status, new RegExp(label));
    assert.match(field.icon, /position: unavailable/);
    assert.match(field.value, /#50/);
    const library = dialFeedback(h, "library", { control: "library" }, 1);
    assert.doesNotMatch(library.status, /Ready/);
    assert.match(library.status, new RegExp(label));
  }
  h.status = "disconnected";
  const field = dialFeedback(h, "dial", settings, 1);
  assert.equal(field.value, "—");
  assert.equal(field.detail, "");
  assert.equal(field.status, "Offline");
});


test("curve-page mode and smoothing feedback reflect Raw versus Calibrated program state", () => {
  const h = client();
  const mode = { operation: "curve.set", curve: "calibrated" };
  const calibrated = h.state.curves.find(curve => curve.curve === "calibrated");
  calibrated.active = true;
  assert.equal(keyFeedback(h, "mode", mode).title, "Data mode\nCalibrated");
  assert.equal(dialFeedback(h, "smooth", { control: "smoothing" }, 1).value, "11 samples");
  calibrated.active = false;
  h.state.controls["smoothing.step"] = { available: false, reason: "unsupported" };
  assert.match(keyFeedback(h, "mode", mode).title, /Data mode\nRaw/);
  const smoothing = dialFeedback(h, "smooth", { control: "smoothing" }, 1);
  assert.equal(smoothing.value, "Raw source values");
  assert.match(smoothing.status, /Raw mode/);
  assert.equal(smoothing.detail, "Select Calibrated");
  h.state.curves = [];
  assert.match(keyFeedback(h, "mode", mode).title, /Data mode\nUnavailable/);
  for (const [index, curve] of ["first", "second", "third", "combined"].entries()) {
    const title = keyFeedback(h, "curve", { operation: "curve.set", curve }).title;
    assert.equal(title.split("\n")[0], index === 3 ? "Combined" : `Curve ${index + 1}`);
  }
});


test("key captions stay within two short lines for long names, values and blocking states", () => {
  const h = client();
  h.state.library.selected.title = "A very long recording name with lots of details";
  h.state.curves[0].label = "A very long translated force direction";
  assert.equal(keyFeedback(h, "marker", { operation: "marker.preview", marker: "gravity", steps: 1 }).title.split("\n")[0], "Gravity +1");
  const examples = JSON.parse(JSON.stringify(snapshot));
  const actions = [
    ...Object.keys(snapshot.controls).map(operation => ({ operation })),
    { operation: "curve.set", curve: "first" },
    { operation: "curve.set", curve: "calibrated" },
  ];
  for (const availability of [{ available: true }, { available: false, reason: "no_recording" }]) {
    h.state.availability = availability;
    for (const settings of actions) for (const status of ["connected", "disconnected", "incompatible"]) {
      h.status = status;
      const title = keyFeedback(h, "key", settings).title;
      assert.ok(title.split("\n").length <= 2, title);
      assert.ok(title.split("\n").every(line => line.length <= 11), title);
    }
  }
  h.state = examples; h.status = "connected";
  assert.equal(keyFeedback(h, "zoom", { operation: "view.selection" }).title, "Zoom\nSelection");
  h.pending = () => true;
  assert.match(keyFeedback(h, "curve", { operation: "curve.set" }).title, /\nPending$/);
  h.error = () => "analysis_failed";
  assert.match(keyFeedback(h, "curve", { operation: "curve.set" }).title, /\nFailed$/);
});


test("Library keys retain readable action labels instead of truncating recording names", () => {
  const h = client();
  const name = "A very long recording name that cannot fit on a key";
  h.state.library.selected.title = name;
  const previous = { operation: "library.move", direction: -1 };
  const next = { operation: "library.move", direction: 1 };
  const open = { operation: "library.open" };
  assert.equal(keyFeedback(h, "previous", previous).title, "Previous\n1/2");
  assert.equal(keyFeedback(h, "next", next).title, "Next\n1/2");
  assert.equal(keyFeedback(h, "open", open).title, "Open\n1/2");
  assert.equal(dialFeedback(h, "library", { control: "library" }, 1).value, name);
  h.state.library.selected.index = 1;
  assert.equal(keyFeedback(h, "open", open).title, "Open\n2/2");
  h.status = "disconnected";
  assert.equal(keyFeedback(h, "previous", previous).title, "Previous\nOffline");
  assert.equal(keyFeedback(h, "next", next).title, "Next\nOffline");
});

test("new-window opening has a compact caption and its own availability", () => {
  const source = client();
  const settings = { operation: "library.open_new_window" };
  assert.equal(keyFeedback(source, "new-window", settings).title, "New\nwindow");
  source.state.controls[settings.operation] = { available: false, reason: "no_selection" };
  assert.equal(keyFeedback(source, "new-window", settings).status, "unavailable");
});

test("Library filter reset uses a short caption and the existing reset icon", () => {
  const source = client();
  const settings = { operation: "library.reset_filters" };
  assert.equal(keyFeedback(source, "reset-filters", settings).title, "Reset\nfilters");
  assert.equal(actionIcon(settings, source.state), "reset");
  source.state.availability = { available: false, reason: "dialog_open" };
  assert.equal(keyFeedback(source, "reset-filters", settings).status, "unavailable");
});
