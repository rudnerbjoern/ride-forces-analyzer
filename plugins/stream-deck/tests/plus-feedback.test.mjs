import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { plusFeedback } from "../dist/plus-feedback.js";
import { pluginOutput } from "../scripts/artifact-path.mjs";

const fixture = JSON.parse(await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8")).messages[0];
const client = () => ({ state: structuredClone(fixture), status: "connected", pending: () => false, error: () => undefined });

test("Plus panoramas retain approved artwork, contiguous crops and the watermark/status axis", async () => {
  const layout = JSON.parse(await readFile(new URL("../devices/layouts/plus.json", import.meta.url), "utf8"));
  const items = Object.fromEntries(layout.items.map(item => [item.key, item]));
  assert.deepEqual(items.background.rect, [0, 0, 200, 100]);
  assert.equal(items.statusIcon.rect[2], 26);
  assert.equal(items.statusIcon.rect[0] + items.statusIcon.rect[2] / 2, 16);
  assert.equal(items.status.font.size, 14);
  assert.equal(items.band.rect[1], 48.1818);
  assert.equal(items.status.rect[1], items.band.rect[1]);
  assert.equal(items.statusIcon.rect[1], items.band.rect[1]);
  assert.equal(items.detail.rect[1], 75);
  assert.equal(items.hint.rect[1], 88);
  const compact = JSON.parse(await readFile(`${pluginOutput}/layouts/plus-compact.json`, "utf8"));
  assert.ok(!compact.items.some(item => item.key === "detail"));
  assert.deepEqual(compact.items.find(item => item.key === "hint").rect, [4, 77, 192, 20]);
  assert.equal(plusFeedback(client(), "position", { control: "position" }, 1).layout, "layouts/plus-compact.json");
  const lines = ["title", "value", "status", "detail", "hint"].map(name => {
    assert.equal(items[name]["text-overflow"], "ellipsis");
    return items[name].rect;
  });
  for (let index = 1; index < lines.length; index++) assert.ok(lines[index][1] >= lines[index - 1][1] + lines[index - 1][3]);
  for (const menu of ["library", "playback", "curves", "markers"]) {
    const source = await readFile(new URL(`../devices/backgrounds/${menu}.svg`, import.meta.url), "utf8");
    const artworkHashes = {
      library: "71b3c4e30a2a101cd3b6de822cba73d866c2c002864ac2c625173cb8ac782d37",
      playback: "ab290e5a20ae0fb68ac5eacae3388bca980d0d5a9d8c3cb6f424ecd47a014b42",
      curves: "3b7621166bc279d1c8799e3d12c01edc32fea51f3bb007817a499daa8a1e19b7",
      markers: "10a40deae7e8575485539537a5d230f089b9c150c019fb3aad0b488dadb9d97b",
    };
    assert.equal(createHash("sha256").update(source.replaceAll("\r\n", "\n")).digest("hex"), artworkHashes[menu]);
    for (let column = 0; column < 4; column++) {
      const tile = await readFile(`${pluginOutput}/layouts/backgrounds/${menu}-${column}.svg`, "utf8");
      assert.match(tile, new RegExp(`viewBox="${column * 200} 0 200 100"`));
      assert.equal(tile.replace(/<svg[^>]*>/, "").replace('<rect width="800" height="100" fill="#080f1b" fill-opacity=".47"/>', "").trim(), source.replace(/<svg[^>]*>/, "").trim());
    }
    if (menu === "library") assert.match(source, /font-size="14".*y="20.1818".*y="34.1818".*y="48.1818"/);
    if (["curves", "markers"].includes(menu)) for (const x of [100, 300, 500, 700]) assert.match(source, new RegExp(`M${x} (?:0v100|6v88)`));
  }
});

test("Plus standalone status symbols retain adopted marker values through preview, pending and failure", () => {
  const h = client();
  for (const phase of ["applied", "preview", "pending", "failed"]) {
    Object.assign(h.state.markers[1], { status: phase, preview: phase === "applied" ? null : { sample: 60, time_seconds: 1.2, label: "00:01.20" },
      request_id: ["pending", "failed"].includes(phase) ? "example" : null, error: phase === "failed" ? "analysis_failed" : null });
    const result = plusFeedback(h, "marker", { control: "marker", marker: "gravity", menu: "markers", column: 1 }, 20);
    assert.equal(result.status.value, phase[0].toUpperCase() + phase.slice(1));
    assert.match(result.detail, /Applied #50/);
    assert.match(result.hint, /Apply.*Discard/);
    assert.doesNotMatch(result.icon, /<circle cx="112"/);
    assert.doesNotMatch(result.status.value, /20|Coarse/);
    assert.match(result.statusIcon, new RegExp(`<title>${phase === "applied" ? "active" : phase}</title>`));
    assert.ok(result.band.includes(result.status.color));
  }
  const unset = plusFeedback(h, "incline", { control: "marker", marker: "incline" }, 1);
  assert.equal(unset.status.value, "Reference unset"); assert.equal(unset.value, "Unset"); assert.equal(unset.detail, "Set in Analyzer");
});

test("Library five-line feedback separates proposal, active label and hints without SVG injection", () => {
  const h = client();
  const name = '<Park & "🎢">\n東京 '.repeat(50);
  h.state.library.park_filter.options[2].label = name;
  const result = plusFeedback(h, "park", { control: "filter", filter: "park", menu: "library", column: 2 }, 20, "Park A");
  assert.equal(result.title, "Park"); assert.equal(result.value, name.replaceAll("\n", " "));
  assert.equal(result.detail, "Active: All parks"); assert.equal(result.hint, "Press: Filter · Touch: All");
  assert.equal(result.layout, "layouts/plus.json");
  assert.equal(result.status.value, "Preview"); assert.doesNotMatch(result.icon + result.statusIcon + result.band, /東京|Park &/);
  assert.equal(result.background, "layouts/backgrounds/library-2.svg");
  h.state.library.park_filter.value = "Park A";
  assert.equal(plusFeedback(h, "park", { control: "filter", filter: "park" }, 1).status.value, "Ready");
});

test("Plus locks, missing data and disconnection never turn decoration into live state", () => {
  const h = client();
  for (const reason of ["input_focus", "dialog_open", "background", "busy"]) {
    h.state.availability = { available: false, reason };
    const result = plusFeedback(h, "position", { control: "position", menu: "curves", column: 3 }, 10);
    assert.match(result.statusIcon, /<title>unavailable/); assert.doesNotMatch(result.status.value, /Medium|10 samples/);
    assert.equal(result.background, "layouts/backgrounds/curves-3.svg");
  }
  h.state.availability = { available: true }; h.state.playback = null;
  h.state.controls["position.step"] = { available: false, reason: "no_recording" };
  assert.equal(plusFeedback(h, "position", { control: "position" }, 1).value, "—");
  h.state.library = null; h.state.target = null; h.state.availability = { available: false, reason: "no_active_window" };
  assert.match(plusFeedback(h, "library", { control: "library" }, 1).statusIcon, /<title>unavailable/);
  h.status = "disconnected"; h.state = undefined;
  const offline = plusFeedback(h, "library", { control: "library" }, 1);
  assert.equal(offline.status.value, "Offline"); assert.equal(offline.value, "—"); assert.equal(offline.detail, "");
  const display = plusFeedback(h, "display", { control: "display", menu: "library", column: 1 }, 1);
  assert.equal(display.background, "layouts/backgrounds/library-1.svg");
  for (const key of ["title", "value", "detail", "hint"]) assert.equal(display[key], "");
  assert.equal(display.status.value, "");
});
