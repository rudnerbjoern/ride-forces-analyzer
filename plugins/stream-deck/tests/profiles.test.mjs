import { TextWriter, Uint8ArrayReader, ZipReader } from "@zip.js/zip.js";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { pathToFileURL } from "node:url";

import { controlSettings } from "../dist/controls.js";
import { dialSettings } from "../dist/device-controls.js";
import { HomeAction } from "../dist/home.js";
import { navigationSettings, PLUS_PAGES } from "../dist/navigation.js";
import { pluginOutput } from "../scripts/artifact-path.mjs";

// cspell:words backtoparent openchild

const uuid = "io.github.rudnerbjoern.ride-forces-analyzer";
const plugin = pathToFileURL(pluginOutput);

test("all bundled profiles use SDK installation defaults and remain editable", async () => {
	const manifest = JSON.parse(await readFile(new URL("manifest.json", plugin), "utf8"));
	assert.deepEqual(
		manifest.Profiles.map((profile) => profile.DeviceType),
		[7, 9, 3],
	);
	for (const profile of manifest.Profiles) {
		assert.equal(profile.Readonly, false);
		assert.equal(profile.AutoInstall, true);
		assert.equal(profile.DontAutoSwitchWhenInstalled, false);
	}
});

test("Plus has six native main pages with a fixed menu, subgroup switches and no folder/system keys", async () => {
	const reader = new ZipReader(
		new Uint8ArrayReader(await readFile(new URL("profiles/plus.streamDeckProfile", plugin))),
	);
	try {
		const entries = await reader.getEntries();
		const root = JSON.parse(
			await entries.find((entry) => /^[^/]+\/manifest.json$/.test(entry.filename)).getData(new TextWriter()),
		);
		const pages = new Map();
		for (const entry of entries.filter((entry) => /\/Profiles\/[^/]+\/manifest.json$/.test(entry.filename))) {
			pages.set(entry.filename.split("/").at(-2).toLowerCase(), JSON.parse(await entry.getData(new TextWriter())));
		}
		assert.equal(root.Device.Model, "20GBD9901");
		assert.equal(root.Pages.Current, root.Pages.Pages[0]);
		assert.equal(pages.size, 7, "Six main pages plus the native empty import template");
		assert.deepEqual(
			root.Pages.Pages.map((id) => pages.get(id).Name),
			["Library", "Playback / Navigate", "Playback / Selection", "Curves", "Markers / Markers", "Markers / View"],
		);
		assert.deepEqual(pages.get(root.Pages.Default).Controllers, [{ Type: "Keypad", Actions: {} }]);
		const identities = new Set();
		const expectedDials = [
			[
				{ control: "library" },
				{ control: "display" },
				{ control: "filter", filter: "park" },
				{ control: "filter", filter: "status" },
			],
			["position", "speed", "view", "zoom_selection"].map((control) => ({ control })),
			[
				...["start", "end"].map((boundary) => ({ control: "selection", boundary })),
				{ control: "view" },
				{ control: "zoom_selection" },
			],
			["smoothing", "combined", "view", "position"].map((control) => ({ control })),
			["start", "gravity", "incline", "end"].map((marker) => ({ control: "marker", marker })),
			["position", "speed", "view", "zoom_selection"].map((control) => ({ control })),
		];
		for (const [index, id] of root.Pages.Pages.entries()) {
			const page = pages.get(id);
			const keys = page.Controllers.find((controller) => controller.Type === "Keypad").Actions;
			const dials = page.Controllers.find((controller) => controller.Type === "Encoder").Actions;
			assert.deepEqual(
				Object.values(dials).map((action) => {
					const { menu, column, ...settings } = action.Settings;
					assert.equal(menu, PLUS_PAGES[index].group);
					assert.equal(column, Object.values(dials).indexOf(action));
					return settings;
				}),
				expectedDials[index],
			);
			for (const dial of Object.values(dials)) assert.ok(dialSettings(dial.Settings));
			if (index === 0) {
				assert.deepEqual(
					Object.keys(dials),
					["0,0", "1,0", "2,0", "3,0"],
					"Library dial 2 only displays its panorama tile",
				);
				assert.deepEqual(
					[0, 1, 2, 3].map((column) => keys[`${column},1`].Settings.operation),
					["library.open.same", "library.open.new", "library.import", "library.filter.reset"],
				);
			} else if (index === 3) {
				assert.deepEqual(
					[0, 1, 2, 3].map((column) => keys[`${column},1`].Settings),
					["first", "second", "third", "calibrated"].map((curve) => ({ operation: "curve.set", curve })),
				);
			} else {
				assert.deepEqual(keys["0,1"].Settings, { operation: "playback.toggle" });
				assert.equal(keys["3,1"].UUID, `${uuid}.step-mode`);
				assert.equal(keys["3,1"].States.length, 3);
				assert.ok(
					keys["3,1"].States.every((state) => state.Title === undefined && state.Image === undefined),
					"Step size captions and icons must remain plugin-owned for the shared 1/10/20 cycle",
				);
			}
			for (const [column, target] of ["library", "playback", "curves", "markers"].entries()) {
				const action = keys[`${column},0`];
				assert.equal(action.UUID, `${uuid}.plus-navigation`);
				assert.deepEqual(action.Settings, { page: index, target });
				assert.equal(action.States.length, 2);
				assert.ok(action.States.every((state) => state.FontSize === 10));
				assert.ok(
					action.States.every((state) => state.Image === undefined && state.Title === undefined),
					"Custom profile images/titles would prevent live SDK feedback from replacing Offline",
				);
			}
			const first = PLUS_PAGES[index].group === "playback" ? 1 : PLUS_PAGES[index].group === "markers" ? 4 : undefined;
			if (first !== undefined)
				for (const [column, target] of [
					[1, first],
					[2, first + 1],
				]) {
					assert.deepEqual(keys[`${column},1`].Settings, { page: index, target });
				}
			for (const action of page.Controllers.flatMap((controller) => Object.values(controller.Actions))) {
				assert.ok(!identities.has(action.ActionID));
				identities.add(action.ActionID);
				assert.ok(
					[`${uuid}.plus-navigation`, `${uuid}.control`, `${uuid}.dial`, `${uuid}.step-mode`].includes(action.UUID),
				);
				if (action.UUID === `${uuid}.plus-navigation`) {
					assert.ok(navigationSettings(action.Settings));
					assert.ok(action.States.every((state) => state.Image === undefined && state.Title === undefined));
				}
				if (action.UUID === `${uuid}.control`) assert.ok(controlSettings(action.Settings));
			}
		}
	} finally {
		await reader.close();
	}
});

test("Neo profile retains reachable native folders, Home and existing key controls", async () => {
	const manifest = JSON.parse(await readFile(new URL("manifest.json", plugin), "utf8"));
	assert.deepEqual(
		manifest.Profiles.map((value) => value.DeviceType),
		[7, 9, 3],
	);
	for (const profile of manifest.Profiles.filter((value) => value.DeviceType === 9)) {
		assert.equal(profile.DontAutoSwitchWhenInstalled, false);
		const reader = new ZipReader(
			new Uint8ArrayReader(await readFile(new URL(`${profile.Name}.streamDeckProfile`, plugin))),
		);
		try {
			const entries = await reader.getEntries();
			const rootEntry = entries.find((entry) => /^[^/]+\/manifest.json$/.test(entry.filename));
			const root = JSON.parse(await rootEntry.getData(new TextWriter()));
			assert.equal(root.Device.Model, profile.DeviceType === 7 ? "20GBD9901" : "20GBJ9901");
			assert.equal(root.Device.UUID, "");
			assert.equal(root.Version, "3.0");
			assert.notEqual(
				root.Pages.Default,
				root.Pages.Current,
				"The native importer requires a distinct default template",
			);
			assert.equal(root.Pages.Pages.length, profile.DeviceType === 7 ? 1 : 2);
			assert.equal(root.Pages.Pages[0], root.Pages.Current);
			const pages = new Map();
			for (const entry of entries.filter((value) => /\/Profiles\/[^/]+\/manifest.json$/.test(value.filename))) {
				pages.set(entry.filename.split("/").at(-2).toLowerCase(), JSON.parse(await entry.getData(new TextWriter())));
			}
			const template = pages.get(root.Pages.Default);
			assert.equal(template.Name, "");
			assert.deepEqual(template.Controllers, [{ Type: "Keypad", Actions: {} }]);
			pages.delete(root.Pages.Default);
			const names = new Map([...pages].map(([id, page]) => [page.Name, id]));
			const keys = (id) => pages.get(id).Controllers.find((value) => value.Type === "Keypad").Actions;
			const start = keys(root.Pages.Current);
			const startPositions = ["1,0", "2,0"];
			assert.equal(pages.get(start[startPositions[0]].Settings.ProfileUUID).Name, "Library");
			assert.equal(pages.get(start[startPositions[1]].Settings.ProfileUUID).Name, "Explorer");
			assert.equal(start["0,1"], undefined);
			const folderImages = [];
			for (const position of startPositions) {
				const image = start[position].States[0].Image;
				assert.notEqual(image, "Images/folder.svg");
				const asset = entries.find((entry) =>
					entry.filename.toLowerCase().endsWith(`/profiles/${root.Pages.Current}/${image.toLowerCase()}`),
				);
				assert.ok(asset);
				const svg = await asset.getData(new TextWriter());
				assert.match(svg, /fill="url\(#/);
				assert.match(svg, /: menu<\/title>/);
				folderImages.push(svg);
			}
			assert.notEqual(folderImages[0], folderImages[1]);
			if (profile.DeviceType !== 7) assert.equal(start["3,1"], undefined);
			{
				assert.equal(start["0,0"].UUID, "com.elgato.streamdeck.system.open");
				assert.deepEqual(
					start["0,0"].Settings,
					{ path: "" },
					"The installed application path is configured by the user",
				);
				assert.equal(start["0,0"].States[0].Title, "Start app");
				const icon = entries.find((entry) =>
					entry.filename
						.toLowerCase()
						.endsWith(`/profiles/${root.Pages.Current}/${start["0,0"].States[0].Image.toLowerCase()}`),
				);
				assert.ok(icon);
				const packagedIcon = await icon.getData(new (await import("@zip.js/zip.js")).Uint8ArrayWriter());
				assert.deepEqual(Buffer.from(packagedIcon), await readFile(new URL("imgs/plugin@2x.png", plugin)));
				assert.equal(start["3,0"].UUID, "com.elgato.streamdeck.system.website");
				assert.deepEqual(start["3,0"].Settings, { path: manifest.URL, openInBrowser: true });
				const websiteIcon = entries.find((entry) =>
					entry.filename
						.toLowerCase()
						.endsWith(`/profiles/${root.Pages.Current}/${start["3,0"].States[0].Image.toLowerCase()}`),
				);
				assert.ok(websiteIcon, "Website must carry its own page-relative icon");
				const websiteSvg = await websiteIcon.getData(new TextWriter());
				assert.match(websiteSvg, /website: menu<\/title>/);
				assert.match(websiteSvg, /fill="url\(#teal\)"/);
				assert.match(websiteSvg, /fill="url\(#gold\)"/);
			}
			const explorer = keys(names.get("Explorer"));
			assert.deepEqual(
				["1,0", "2,0", "1,1"].map((position) => pages.get(explorer[position].Settings.ProfileUUID).Name),
				["Playback", "View / Curves", "Markers"],
			);
			const markers = keys(names.get("Markers"));
			if (profile.DeviceType === 9)
				assert.deepEqual(
					["1,0", "2,0", "1,1", "2,1"].map((position) => markers[position].States[0].Title),
					["Start", "Gravity", "Incline", "End"],
				);

			const visited = new Set();
			const actionIds = new Set();
			const operations = new Set();
			/**
			 * Traverse native profile pages and validate action ownership and navigation.
			 * @param {string} id Native profile page UUID to visit.
			 */
			function visit(id) {
				assert.ok(!visited.has(id), "Native folder tree must not cycle or have multiple parents");
				visited.add(id);
				const actions = keys(id);
				if (id !== root.Pages.Current) {
					assert.equal(
						actions["0,0"].UUID,
						pages.get(id).Name === "Quick controls" ? `${uuid}.home` : "com.elgato.streamdeck.profile.backtoparent",
					);
					if (profile.DeviceType === 9) assert.equal(actions["3,1"].UUID, `${uuid}.home`);
					else
						assert.ok(
							Object.values(actions).every((action) => action.UUID !== `${uuid}.home`),
							"Plus leaves Home unassigned",
						);
					for (const position of profile.DeviceType === 9 ? ["0,0", "3,1"] : ["0,0"]) {
						assert.ok(
							entries.some((entry) =>
								entry.filename
									.toLowerCase()
									.endsWith(`/profiles/${id}/${actions[position].States[0].Image.toLowerCase()}`),
							),
						);
					}
				}
				for (const [position, action] of Object.entries(actions)) {
					assert.match(position, /^[0-3],[01]$/);
					assert.ok(!actionIds.has(action.ActionID));
					actionIds.add(action.ActionID);
					if (action.UUID === "com.elgato.streamdeck.profile.openchild") {
						assert.ok(pages.has(action.Settings.ProfileUUID), "Folder destination must exist");
						assert.ok(
							entries.some((entry) =>
								entry.filename.toLowerCase().endsWith(`/profiles/${id}/${action.States[0].Image.toLowerCase()}`),
							),
							"Folder icons must be relative to their own page",
						);
						visit(action.Settings.ProfileUUID);
					} else if (action.UUID === `${uuid}.control`) {
						assert.ok(controlSettings(action.Settings), "Persisted commands must satisfy the existing key contract");
						operations.add(action.Settings.operation);
						assert.ok(action.States.every((state) => state.FontSize === 10 && state.TitleAlignment === "bottom"));
					} else if (action.UUID.startsWith("com.elgato.streamdeck.system.")) {
						assert.equal(id, root.Pages.Current, "Native system actions belong only on Start");
						assert.ok(
							["com.elgato.streamdeck.system.open", "com.elgato.streamdeck.system.website"].includes(action.UUID),
						);
					} else {
						assert.ok(
							[`${uuid}.home`, `${uuid}.step-mode`, "com.elgato.streamdeck.profile.backtoparent"].includes(action.UUID),
						);
					}
				}
			}
			root.Pages.Pages.forEach(visit);
			assert.equal(visited.size, pages.size, "Every bundled menu must be reachable with keys");
			for (const operation of [
				"library.move",
				"library.open.same",
				"library.open.new",
				"library.import",
				"playback.toggle",
				"position.step",
				"playback.speed.step",
				"playback.speed.reset",
				"smoothing.step",
				"smoothing.reset",
				"view.zoom",
				"view.reset",
				"curve.set",
			]) {
				assert.ok(operations.has(operation), `Missing key alternative: ${operation}`);
			}
			const library = keys(names.get("Library"));
			assert.equal(library["0,1"].Settings.operation, "library.import");
			assert.equal(library["2,1"].Settings.operation, "library.open.new");
			if (profile.DeviceType === 9) assert.equal(library["1,1"].Settings.operation, "library.open.same");
			if (profile.DeviceType === 9)
				for (const marker of ["start", "gravity", "incline", "end"]) {
					const editor = keys(names.get(`${marker.charAt(0).toUpperCase()}${marker.slice(1)} marker`));
					assert.deepEqual(
						["1,0", "1,1", "2,1", "2,0"].map((position) => editor[position].Settings),
						[-10, -1, 1, 10].map((steps) => ({ operation: "marker.preview", marker, steps })),
					);
					assert.deepEqual(editor["0,1"].Settings, { operation: "marker.discard", marker });
					assert.deepEqual(editor["3,0"].Settings, { operation: "marker.apply", marker });
				}
			{
				assert.equal(pages.get(root.Pages.Pages[1]).Name, "Quick controls");
				const quick = keys(root.Pages.Pages[1]);
				assert.deepEqual(
					["1,0", "2,0", "3,0", "0,1", "1,1", "2,1"].map((position) => quick[position].Settings.operation),
					["playback.toggle", "view.zoom", "view.zoom", "view.reset", "view.selection", "playback.speed.reset"],
				);
				for (const page of pages.values()) {
					const bar = page.Controllers.find((value) => value.Type === "Neo").Actions["1,0"];
					assert.equal(bar.UUID, `${uuid}.infobar`);
					if (page.Name.endsWith(" marker")) assert.equal(bar.Settings.marker, page.Name.split(" ")[0].toLowerCase());
					assert.ok(!page.Controllers.some((value) => value.Type === "Encoder"));
				}
			}
		} finally {
			await reader.close();
		}
	}
});

test("prepared layouts fit the Plus/Neo canvases and every field used by feedback exists", async () => {
	for (const [name, width, height, controller] of [
		["plus", 200, 100, "Encoder"],
		["neo", 232, 50, "Neo"],
	]) {
		const layout = JSON.parse(await readFile(new URL(`layouts/${name}.json`, plugin), "utf8"));
		assert.equal(layout.controller, controller);
		const keys = new Set(layout.items.map((item) => item.key));
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
	const home = new HomeAction(async (...arguments_) => {
		calls.push(arguments_);
	});
	for (const [type, id] of [
		[7, "plus-device"],
		[9, "neo-device"],
		[0, "unsupported"],
	]) {
		await home.onKeyDown({
			action: {
				device: { type, id },
				async showAlert() {
					alerts++;
				},
			},
			payload: { settings: {} },
		});
	}
	assert.deepEqual(calls, [
		["plus-device", "profiles/plus", 0],
		["neo-device", "profiles/neo", 0],
	]);
	assert.equal(alerts, 1);
});

test("Mobile preview keeps its entire reachable profile within six keys and existing commands", async () => {
	const reader = new ZipReader(
		new Uint8ArrayReader(await readFile(new URL("profiles/mobile.streamDeckProfile", plugin))),
	);
	try {
		const entries = await reader.getEntries();
		const root = JSON.parse(
			await entries.find((entry) => /^[^/]+\/manifest.json$/.test(entry.filename)).getData(new TextWriter()),
		);
		assert.equal(root.Device.Model, "VSD2/WiFi");
		assert.equal(root.Name, "Ride Forces Analyzer Mobile Preview");
		assert.deepEqual(root.Pages.Pages, [root.Pages.Current]);
		const pages = new Map();
		for (const entry of entries.filter((entry) => /\/Profiles\/[^/]+\/manifest.json$/.test(entry.filename))) {
			const page = JSON.parse(await entry.getData(new TextWriter()));
			if (page.Name) pages.set(entry.filename.split("/").at(-2).toLowerCase(), page);
		}
		assert.deepEqual(
			[...pages.values()].map((page) => page.Name),
			["Start", "Library", "Playback", "View"],
		);
		const visited = new Set(),
			operations = new Set();
		/**
		 * Traverse native profile pages and validate action ownership and navigation.
		 * @param {string} id Native profile page UUID to visit.
		 */
		function visit(id) {
			assert.ok(!visited.has(id), "Folders must have one parent and no cycles");
			visited.add(id);
			const page = pages.get(id);
			assert.deepEqual(
				page.Controllers.map((controller) => controller.Type),
				["Keypad"],
			);
			const keys = page.Controllers[0].Actions;
			assert.ok(Object.keys(keys).length <= 6);
			if (page.Name !== "Start") {
				assert.equal(keys["0,0"].UUID, "com.elgato.streamdeck.profile.backtoparent");
				assert.ok(Object.values(keys).every((action) => action.UUID !== `${uuid}.home`));
			}
			for (const [position, action] of Object.entries(keys)) {
				assert.match(position, /^[0-2],[01]$/);
				if (action.UUID.endsWith(".control")) {
					assert.ok(controlSettings(action.Settings));
					operations.add(action.Settings.operation);
				} else {
					const image = action.States[0].Image;
					assert.ok(
						entries.some((entry) => entry.filename.toLowerCase().endsWith(`/profiles/${id}/${image.toLowerCase()}`)),
					);
				}
				if (action.UUID === "com.elgato.streamdeck.profile.openchild") visit(action.Settings.ProfileUUID);
			}
		}
		visit(root.Pages.Current);
		assert.equal(visited.size, 4);
		assert.deepEqual([...operations].sort(), [
			"library.import",
			"library.move",
			"library.open.new",
			"library.open.same",
			"playback.toggle",
			"position.step",
			"view.reset",
			"view.selection",
			"view.zoom",
		]);
		const mobileKeys = (name) => [...pages.values()].find((page) => page.Name === name).Controllers[0].Actions;
		const library = mobileKeys("Library");
		// Landscape keeps Back first and Previous/Next side by side.
		assert.equal(library["0,0"].UUID, "com.elgato.streamdeck.profile.backtoparent");
		assert.equal(library["0,1"].Settings.operation, "library.import");
		assert.deepEqual(library["1,0"].Settings, { operation: "library.move", direction: -1 });
		assert.deepEqual(library["2,0"].Settings, { operation: "library.move", direction: 1 });
		assert.equal(library["1,1"].Settings.operation, "library.open.same");
		assert.equal(library["2,1"].Settings.operation, "library.open.new");
		assert.equal(mobileKeys("Playback")["2,1"].Settings.operation, "view.reset");
		assert.equal(mobileKeys("View")["2,1"].Settings.operation, "playback.toggle");
		const start = pages.get(root.Pages.Current).Controllers[0].Actions;
		assert.equal(start["0,0"].UUID, "com.elgato.streamdeck.system.open");
		assert.equal(start["0,0"].Settings.path, "");
		assert.equal(start["0,1"].UUID, "com.elgato.streamdeck.system.website");
	} finally {
		await reader.close();
	}
});
