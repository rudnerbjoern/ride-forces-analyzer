import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { TextWriter, Uint8ArrayReader, ZipReader } from "@zip.js/zip.js";

import { HomeAction } from "../dist/home.js";
import { controlSettings } from "../dist/controls.js";

// cspell:words backtoparent openchild

const uuid = "io.github.rudnerbjoern.ride-forces-analyzer";
const plugin = new URL(`../${uuid}.sdPlugin/`, import.meta.url);

test("bundled device profiles provide reachable native menus, fixed navigation and existing key controls", async () => {
  const manifest = JSON.parse(await readFile(new URL("manifest.json", plugin), "utf8"));
  assert.deepEqual(manifest.Profiles.map(value => value.DeviceType), [7, 9]);
  for (const profile of manifest.Profiles) {
    assert.equal(profile.DontAutoSwitchWhenInstalled, true);
    const reader = new ZipReader(new Uint8ArrayReader(await readFile(new URL(`${profile.Name}.streamDeckProfile`, plugin))));
    try {
      const entries = await reader.getEntries();
      const rootEntry = entries.find(entry => /^[^/]+\/manifest.json$/.test(entry.filename));
      const root = JSON.parse(await rootEntry.getData(new TextWriter()));
      assert.equal(root.Device.Model, profile.DeviceType === 7 ? "20GBD9901" : "20GBJ9901");
      assert.equal(root.Device.UUID, "");
      assert.equal(root.Version, "3.0");
      assert.equal(root.Pages.Default, root.Pages.Current);
      const pages = new Map();
      for (const entry of entries.filter(value => /\/Profiles\/[^/]+\/manifest.json$/.test(value.filename))) {
        pages.set(entry.filename.split("/").at(-2).toLowerCase(), JSON.parse(await entry.getData(new TextWriter())));
      }
      const names = new Map([...pages].map(([id, page]) => [page.Name, id]));
      const keys = id => pages.get(id).Controllers.find(value => value.Type === "Keypad").Actions;
      const start = keys(root.Pages.Default);
      assert.equal(pages.get(start["0,0"].Settings.ProfileUUID).Name, "Library");
      assert.equal(pages.get(start["1,0"].Settings.ProfileUUID).Name, "Explorer");
      assert.equal(start["0,1"], undefined);
      assert.equal(start["3,1"], undefined);
      const explorer = keys(names.get("Explorer"));
      assert.deepEqual(["1,0", "2,0", "3,0"].map(position => pages.get(explorer[position].Settings.ProfileUUID).Name),
        ["Playback", "View / Curves", "Markers"]);
      const markers = keys(names.get("Markers"));
      assert.deepEqual(["1,0", "2,0", "3,0", "0,1"].map(position => markers[position].States[0].Title),
        ["Start", "Gravity", "Incline", "End"]);

      const visited = new Set();
      const actionIds = new Set();
      const operations = new Set();
      function visit(id) {
        assert.ok(!visited.has(id), "Native folder tree must not cycle or have multiple parents");
        visited.add(id);
        const actions = keys(id);
        if (id !== root.Pages.Default) {
          assert.equal(actions["0,0"].UUID, "com.elgato.streamdeck.profile.backtoparent");
          assert.equal(actions["3,1"].UUID, `${uuid}.home`);
        }
        for (const [position, action] of Object.entries(actions)) {
          assert.match(position, /^[0-3],[01]$/);
          assert.ok(!actionIds.has(action.ActionID));
          actionIds.add(action.ActionID);
          if (action.UUID === "com.elgato.streamdeck.profile.openchild") {
            assert.ok(pages.has(action.Settings.ProfileUUID), "Folder destination must exist");
            assert.ok(entries.some(entry => entry.filename.toLowerCase().endsWith(
              `/profiles/${id}/${action.States[0].Image.toLowerCase()}`)), "Folder icons must be relative to their own page");
            visit(action.Settings.ProfileUUID);
          } else if (action.UUID === `${uuid}.control`) {
            assert.ok(controlSettings(action.Settings), "Persisted commands must satisfy the existing key contract");
            assert.ok(!action.Settings.operation.startsWith("marker."), "Device marker editors have separate implementation steps");
            operations.add(action.Settings.operation);
          } else {
            assert.ok([`${uuid}.home`, "com.elgato.streamdeck.profile.backtoparent"].includes(action.UUID));
          }
        }
        assert.deepEqual(pages.get(id).Controllers.map(value => value.Type), ["Keypad"]);
      }
      visit(root.Pages.Default);
      assert.equal(visited.size, pages.size, "Every bundled menu must be reachable with keys");
      for (const operation of ["library.move", "library.open", "library.import", "playback.toggle", "position.step",
        "playback.speed.step", "playback.speed.reset", "smoothing.step", "smoothing.reset", "view.zoom", "view.reset", "curve.set"]) {
        assert.ok(operations.has(operation), `Missing key alternative: ${operation}`);
      }
      const library = keys(names.get("Library"));
      assert.equal(library[profile.DeviceType === 7 ? "1,0" : "0,1"].Settings.operation, "library.import");
    } finally { await reader.close(); }
  }
});

test("Home selects only the invoking device's bundled Start page without an application connection", async () => {
  const calls = [];
  let alerts = 0;
  const home = new HomeAction(async (...arguments_) => { calls.push(arguments_); });
  for (const [type, id] of [[7, "plus-device"], [9, "neo-device"], [0, "unsupported"]]) {
    await home.onKeyDown({ action: { device: { type, id }, async showAlert() { alerts++; } }, payload: { settings: {} } });
  }
  assert.deepEqual(calls, [["plus-device", "profiles/plus", 0], ["neo-device", "profiles/neo", 0]]);
  assert.equal(alerts, 1);
});
