import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { TextWriter, Uint8ArrayReader, ZipReader } from "@zip.js/zip.js";
import { pathToFileURL } from "node:url";
import { pluginOutput } from "../scripts/artifact-path.mjs";

import { HomeAction } from "../dist/home.js";
import { controlSettings } from "../dist/controls.js";

// cspell:words backtoparent openchild

const uuid = "io.github.rudnerbjoern.ride-forces-analyzer";
const plugin = pathToFileURL(pluginOutput);

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
      assert.notEqual(root.Pages.Default, root.Pages.Current, "The native importer requires a distinct default template");
      assert.deepEqual(root.Pages.Pages, [root.Pages.Current]);
      const pages = new Map();
      for (const entry of entries.filter(value => /\/Profiles\/[^/]+\/manifest.json$/.test(value.filename))) {
        pages.set(entry.filename.split("/").at(-2).toLowerCase(), JSON.parse(await entry.getData(new TextWriter())));
      }
      const template = pages.get(root.Pages.Default);
      assert.equal(template.Name, "");
      assert.deepEqual(template.Controllers, [{ Type: "Keypad", Actions: {} }]);
      pages.delete(root.Pages.Default);
      const names = new Map([...pages].map(([id, page]) => [page.Name, id]));
      const keys = id => pages.get(id).Controllers.find(value => value.Type === "Keypad").Actions;
      const start = keys(root.Pages.Current);
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
        if (id !== root.Pages.Current) {
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
            operations.add(action.Settings.operation);
          } else {
            assert.ok([`${uuid}.home`, `${uuid}.step-mode`, "com.elgato.streamdeck.profile.backtoparent"].includes(action.UUID));
          }
        }
      }
      visit(root.Pages.Current);
      assert.equal(visited.size, pages.size, "Every bundled menu must be reachable with keys");
      for (const operation of ["library.move", "library.open", "library.import", "playback.toggle", "position.step",
        "playback.speed.step", "playback.speed.reset", "smoothing.step", "smoothing.reset", "view.zoom", "view.reset", "curve.set"]) {
        assert.ok(operations.has(operation), `Missing key alternative: ${operation}`);
      }
      const library = keys(names.get("Library"));
      assert.equal(library[profile.DeviceType === 7 ? "1,0" : "0,1"].Settings.operation, "library.import");
      for (const marker of ["start", "gravity", "incline", "end"]) {
        const editor = keys(names.get(`${marker.charAt(0).toUpperCase()}${marker.slice(1)} marker`));
        assert.deepEqual(["1,0", "2,0", "3,0", "0,1"].map(position => editor[position].Settings),
          [-10, -1, 1, 10].map(steps => ({ operation: "marker.preview", marker, steps })));
        assert.deepEqual(editor["1,1"].Settings, { operation: "marker.discard", marker });
        assert.deepEqual(editor["2,1"].Settings, { operation: "marker.apply", marker });
      }
      if (profile.DeviceType === 7) {
        const dials = name => pages.get(names.get(name)).Controllers.find(value => value.Type === "Encoder").Actions;
        assert.deepEqual(dials("Library")["0,0"].Settings, { control: "library" });
        assert.deepEqual(Object.values(dials("Playback")).map(value => value.Settings.control), ["position", "view", "smoothing", "speed"]);
        assert.deepEqual(Object.values(dials("Markers")).map(value => value.Settings.marker), ["start", "gravity", "incline", "end"]);
        for (const name of ["Playback", "Markers"]) assert.equal(keys(names.get(name))["1,1"].UUID, `${uuid}.step-mode`);
        assert.ok([...pages.values()].every(page => !page.Controllers.some(value => value.Type === "Neo")));
      } else {
        for (const page of pages.values()) {
          const bar = page.Controllers.find(value => value.Type === "Neo").Actions["1,0"];
          assert.equal(bar.UUID, `${uuid}.infobar`);
          if (page.Name.endsWith(" marker")) assert.equal(bar.Settings.marker, page.Name.split(" ")[0].toLowerCase());
          assert.ok(!page.Controllers.some(value => value.Type === "Encoder"));
        }
      }
    } finally { await reader.close(); }
  }
});

test("prepared layouts fit the Plus/Neo canvases and every field used by feedback exists", async () => {
  for (const [name, width, height, controller] of [["plus", 200, 100, "Encoder"], ["neo", 232, 50, "Neo"]]) {
    const layout = JSON.parse(await readFile(new URL(`layouts/${name}.json`, plugin), "utf8"));
    assert.equal(layout.controller, controller);
    const keys = new Set(layout.items.map(item => item.key));
    assert.equal(keys.size, layout.items.length);
    for (const key of ["icon", "title", "value", "status"]) assert.ok(keys.has(key));
    for (const item of layout.items) {
      const [x, y, w, h] = item.rect;
      assert.ok(x >= 0 && y >= 0 && w > 0 && h > 0 && x + w <= width && y + h <= height);
    }
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
