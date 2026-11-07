import assert from "node:assert/strict";
import test from "node:test";
import streamDeck from "@elgato/streamdeck";

import { PlusNavigationAction, navigationFeedback, navigationSettings } from "../dist/navigation.js";

function key(device, page, target, type = 7) {
  const output = { states: [], images: [], alerts: 0 };
  return { output, action: { id: `${device}/${page}/${target}`, device: { id: device, type }, isKey: () => true,
    async setState(value) { output.states.push(value); }, async setImage(value) { output.images.push(value); },
    async setTitle() {}, async showAlert() { output.alerts++; } }, payload: { settings: { page, target } } };
}

test("Plus navigation uses only confirmed appearances, including swipes, and remembers groups per device", async t => {
  t.mock.method(streamDeck.logger, "info", () => {});
  const calls = [];
  const action = new PlusNavigationAction(async (...args) => { calls.push(args); });
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

test("Plus navigation rejects invalid settings/devices and does not confirm failed or overlapping requests", async t => {
  t.mock.method(streamDeck.logger, "info", () => {});
  t.mock.method(streamDeck.logger, "warn", () => {});
  for (const settings of [{}, { page: "1", target: "library" }, { page: true, target: "library" },
    { page: 6, target: "library" }, { page: -1, target: "library" }, { page: 1.5, target: "library" },
    { page: 0, target: 2 }, { page: 1, target: 5 }, { page: 4, target: 2 }, { page: 0, target: "unknown" }]) {
    assert.equal(navigationSettings(settings), undefined);
  }
  for (const [page, target] of [[0, "library"], [1, 2], [2, 1], [4, 5], [5, 4]]) {
    assert.deepEqual(navigationSettings({ page, target }), { page, target });
  }
  let finish;
  const calls = [];
  const action = new PlusNavigationAction((...args) => {
    calls.push(args);
    return new Promise((resolve, reject) => { finish = { resolve, reject }; });
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
