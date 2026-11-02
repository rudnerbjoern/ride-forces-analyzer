import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { TextReader, Uint8ArrayWriter, ZipWriter } from "@zip.js/zip.js";

// cspell:words backtoparent openchild

const uuid = "io.github.rudnerbjoern.ride-forces-analyzer";
const plugin = fileURLToPath(new URL(`../${uuid}.sdPlugin/`, import.meta.url));

// Native folders own navigation; application controls reuse the configurable SDK action.
const folder = (title, page) => ({ title, page });
const control = (operation, settings = {}) => ({ operation, ...settings });
const pages = {
  start: { name: "Start", keys: [folder("Library", "library"), folder("Explorer", "explorer")] },
  library: { name: "Library", keys: [control("library.move", { direction: -1 }),
    control("library.move", { direction: 1 }), control("library.open"), control("library.import")] },
  explorer: { name: "Explorer", keys: [folder("Playback", "playback"),
    folder("View / Curves", "view"), folder("Markers", "markers")] },
  playback: { name: "Playback", keys: [control("playback.toggle"), folder("Position", "position"),
    folder("Smoothing", "smoothing"), folder("Speed", "speed")] },
  position: { name: "Position", keys: [-10, -1, 1, 10].map(steps => control("position.step", { steps })),
    extra: [control("view.zoom", { direction: -1 }), control("view.zoom", { direction: 1 })] },
  smoothing: { name: "Smoothing", keys: [control("smoothing.step", { direction: -1 }),
    control("smoothing.reset"), control("smoothing.step", { direction: 1 })] },
  speed: { name: "Playback speed", keys: [control("playback.speed.step", { direction: -1 }),
    control("playback.speed.reset"), control("playback.speed.step", { direction: 1 })] },
  view: { name: "View / Curves", keys: [control("curve.set", { curve: "first" }),
    control("curve.set", { curve: "second" }), control("curve.set", { curve: "third" }), control("view.reset")],
    extra: [control("curve.set", { curve: "calibrated" }), control("curve.set", { curve: "combined" })] },
  markers: { name: "Markers", keys: [folder("Start", "marker-start"), folder("Gravity", "marker-gravity"),
    folder("Incline", "marker-incline"), folder("End", "marker-end")] },
  // Device-specific marker editor bindings belong to their own implementation steps.
  "marker-start": { name: "Start marker", keys: [] },
  "marker-gravity": { name: "Gravity marker", keys: [] },
  "marker-incline": { name: "Incline marker", keys: [] },
  "marker-end": { name: "End marker", keys: [] },
};

/** Stable identities keep rebuilt bundled profiles tied to the same native pages. */
function identity(value) {
  const bytes = createHash("sha256").update(`${uuid}/${value}`).digest().subarray(0, 16);
  bytes[6] = (bytes[6] & 15) | 80;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function key(id, name, action, settings, title) {
  return { ActionID: identity(id), LinkedTitle: true, Name: name, Settings: settings, State: 0,
    States: title ? [{ Title: title, TitleAlignment: "bottom", FontSize: 10, ShowTitle: true }] : [{}], UUID: action };
}

/** Assemble Plus and Neo archives from shared native folder/key assignments. */
export async function buildProfiles() {
  await mkdir(path.join(plugin, "profiles"), { recursive: true });
  for (const [device, model] of [["plus", "20GBD9901"], ["neo", "20GBJ9901"]]) {
    const profileId = identity(device);
    const root = `${profileId.toUpperCase()}.sdProfile`;
    const pageId = name => identity(`${device}/${name}`);
    const writer = new ZipWriter(new Uint8ArrayWriter(), { level: 0, lastModDate: new Date("2026-01-01T00:00:00Z") });
    const add = (filename, data) => writer.add(`${root}/${filename}`, new TextReader(JSON.stringify(data, null, 2) + "\n"));
    await add("manifest.json", { Device: { Model: model, UUID: "" }, Name: `Ride Forces Analyzer ${device === "plus" ? "+" : "Neo"}`,
      Pages: { Current: pageId("start"), Default: pageId("start"), Pages: [pageId("start")] }, Version: "3.0" });
    for (const [name, page] of Object.entries(pages)) {
      const actions = {};
      const put = (definition, index) => {
        const coordinate = `${index % 4},${Math.floor(index / 4)}`;
        const id = `${device}/${name}/${coordinate}`;
        if (definition.page) {
          actions[coordinate] = key(id, "Create Folder", "com.elgato.streamdeck.profile.openchild",
            { ProfileUUID: pageId(definition.page) }, definition.title);
          actions[coordinate].States[0].Image = "Images/folder.svg";
        } else {
          actions[coordinate] = key(id, "Analyzer control", `${uuid}.control`, definition);
          actions[coordinate].States.push({});
        }
      };
      const keys = device === "plus" && name === "library"
        ? [page.keys[3], ...page.keys.slice(0, 3)] : page.keys;
      keys.forEach((definition, index) => put(definition, name === "start" ? index : index + 1));
      (page.extra ?? []).forEach((definition, index) => put(definition, index + 5));
      if (name !== "start") {
        // Stream Deck forces native folder Back to key 1 during import.
        actions["0,0"] = key(`${device}/${name}/back`, "Parent Folder",
          "com.elgato.streamdeck.profile.backtoparent", {}, "Back");
        actions["3,1"] = key(`${device}/${name}/home`, "Home", `${uuid}.home`, {}, "Home");
      }
      await add(`Profiles/${pageId(name).toUpperCase()}/manifest.json`,
        { Controllers: [{ Type: "Keypad", Actions: actions }], Icon: "", Name: page.name });
      if (keys.some(definition => definition.page)) {
        await writer.add(`${root}/Profiles/${pageId(name).toUpperCase()}/Images/folder.svg`,
          new TextReader(await readFile(path.join(plugin, "imgs/folder.svg"), "utf8")));
      }
    }
    await writeFile(path.join(plugin, `profiles/${device}.streamDeckProfile`), await writer.close());
  }
  console.log("Built Plus and Neo native folder profiles.");
}
