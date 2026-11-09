import { TextReader, Uint8ArrayReader, Uint8ArrayWriter, ZipWriter } from "@zip.js/zip.js";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

// cspell:words backtoparent openchild

const uuid = "io.github.rudnerbjoern.ride-forces-analyzer";

// Native folders own navigation; application controls reuse the configurable SDK action.
const folder = (title, page) => ({ title, page });
let profileLanguage = "en";
const control = (operation, settings = {}) => ({ operation, ...settings });
const pages = {
	start: { name: "Start", keys: [folder("Library", "library"), folder("Explorer", "explorer")] },
	library: {
		name: "Library",
		keys: [
			control("library.move", { direction: -1 }),
			control("library.move", { direction: 1 }),
			control("library.open.same"),
			control("library.import"),
			control("library.open.new"),
		],
	},
	explorer: {
		name: "Explorer",
		keys: [
			folder("Playback", "playback"),
			folder("View / Curves", "view"),
			folder("Markers", "markers"),
			folder("Selection", "selection"),
		],
	},
	playback: {
		name: "Playback",
		keys: [
			control("playback.toggle"),
			folder("Position", "position"),
			folder("Smoothing", "smoothing"),
			folder("Speed", "speed"),
		],
	},
	quick: {
		name: "Quick controls",
		keys: [
			control("playback.toggle"),
			control("view.zoom", { direction: -1 }),
			control("view.zoom", { direction: 1 }),
			control("view.reset"),
			control("view.selection"),
			control("playback.speed.reset"),
		],
	},
	selection: { name: "Selection", keys: [control("view.selection")] },
	position: {
		name: "Position",
		keys: [-10, -1, 1, 10].map((steps) => control("position.step", { steps })),
		extra: [control("view.zoom", { direction: -1 }), control("view.zoom", { direction: 1 })],
	},
	smoothing: {
		name: "Smoothing",
		keys: [
			control("smoothing.step", { direction: -1 }),
			control("smoothing.reset"),
			control("smoothing.step", { direction: 1 }),
		],
	},
	speed: {
		name: "Playback speed",
		keys: [
			control("playback.speed.step", { direction: -1 }),
			control("playback.speed.reset"),
			control("playback.speed.step", { direction: 1 }),
		],
	},
	view: {
		name: "View / Curves",
		keys: [
			control("curve.set", { curve: "first" }),
			control("curve.set", { curve: "second" }),
			control("curve.set", { curve: "third" }),
			control("view.reset"),
		],
		extra: [control("curve.set", { curve: "calibrated" }), control("curve.set", { curve: "combined" })],
	},
	markers: {
		name: "Markers",
		keys: [
			folder("Start", "marker.start"),
			folder("Gravity", "marker.gravity"),
			folder("Incline", "marker.incline"),
			folder("End", "marker.end"),
		],
	},
	"marker.start": { name: "Start marker", keys: [] },
	"marker.gravity": { name: "Gravity marker", keys: [] },
	"marker.incline": { name: "Incline marker", keys: [] },
	"marker.end": { name: "End marker", keys: [] },
};

// Keep the six-key Mobile preview limited to browsing and playback/view navigation.
const mobilePages = {
	start: { name: "Start", keys: [folder("Library", "library"), folder("Playback", "playback")] },
	library: pages.library,
	playback: {
		name: "Playback",
		keys: [
			control("playback.toggle"),
			folder("View", "view"),
			control("position.step", { steps: -1 }),
			control("position.step", { steps: 1 }),
			control("view.reset"),
		],
	},
	view: {
		name: "View",
		keys: [
			control("view.zoom", { direction: -1 }),
			control("view.zoom", { direction: 1 }),
			control("view.reset"),
			control("view.selection"),
			control("playback.toggle"),
		],
	},
};

/**
 * Derive a stable native profile or action identity from its logical path.
 * @param {string} value Logical device, page or action path.
 * @returns {string} Deterministic UUID for the supplied path.
 */
function identity(value) {
	const bytes = createHash("sha256").update(`${uuid}/${value}`).digest().subarray(0, 16);
	bytes[6] = (bytes[6] & 15) | 80;
	bytes[8] = (bytes[8] & 63) | 128;
	const hex = bytes.toString("hex");
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * Create a native key assignment with a stable identity and optional title.
 * @param {string} id Logical action path used to derive its UUID.
 * @param {string} name Native action display name.
 * @param {string} action Registered SDK or built-in action UUID.
 * @param {object} settings Settings stored with the key assignment.
 * @param {string} title Caption override, or an empty value for plugin-owned captions.
 * @returns {object} Native key action definition.
 */
function key(id, name, action, settings, title) {
	return {
		ActionID: identity(`${id}${profileLanguage === "en" ? "" : `/${profileLanguage}`}`),
		LinkedTitle: true,
		Name: name,
		Settings: settings,
		State: 0,
		States: title ? [{ Title: title, TitleAlignment: "bottom", FontSize: 10, ShowTitle: true }] : [{}],
		UUID: action,
	};
}

/**
 * Build the bundled Plus, Neo and Mobile profile archives.
 * @param {string} plugin Output plugin directory containing the assembled manifest.
 */
export async function buildProfiles(plugin) {
	const { keyImage } = await import("../dist/feedback.js");
	const { PLUS_PAGES, navigationFeedback } = await import("../dist/navigation.js");
	const { LANGUAGES, displayText, setLanguage, translate } = await import("../dist/localization.js");
	const metadata = JSON.parse(await readFile(path.join(plugin, "manifest.json"), "utf8"));
	await mkdir(path.join(plugin, "profiles"), { recursive: true });
	for (const language of LANGUAGES) {
		setLanguage(language);
		profileLanguage = language;
		for (const [device, model] of [
			["plus", "20GBD9901"],
			["neo", "20GBJ9901"],
			["mobile", "VSD2/WiFi"],
		]) {
			const columns = device === "mobile" ? 3 : 4;
			const homePosition = `${columns - 1},1`;
			const profileId = identity(`${device}${language === "en" ? "" : `/${language}`}`);
			const root = `${profileId.toUpperCase()}.sdProfile`;
			const pageId = (name) => identity(`${device}/${name}${language === "en" ? "" : `/${language}`}`);
			const writer = new ZipWriter(new Uint8ArrayWriter(), { level: 0, lastModDate: new Date("2026-01-01T00:00:00Z") });
			const add = (filename, data) => {
				if (data.Name)
					data.Name = `${displayText(data.Name)}${filename === "manifest.json" && language !== "en" ? ` (${language.toUpperCase()})` : ""}`;
				for (const controller of data.Controllers ?? [])
					for (const action of Object.values(controller.Actions)) {
						action.Name = translate(action.Name);
						for (const state of action.States ?? []) if (state.Title) state.Title = displayText(state.Title);
					}
				return writer.add(`${root}/${filename}`, new TextReader(JSON.stringify(data, null, 2) + "\n"));
			};
			await add("manifest.json", {
				Device: { Model: model, UUID: "" },
				Name: `Ride Forces Analyzer ${device === "plus" ? "+" : device === "neo" ? "Neo" : "Mobile Preview"}`,
				Pages: {
					Current: pageId(device === "plus" ? "library" : "start"),
					Default: pageId("default"),
					Pages:
						device === "plus"
							? PLUS_PAGES.map((page) => pageId(page.id))
							: device === "neo"
								? [pageId("start"), pageId("quick")]
								: [pageId("start")],
				},
				Version: "3.0",
			});
			// The native importer reserves Default for a separate empty page template.
			await add(`Profiles/${pageId("default").toUpperCase()}/manifest.json`, {
				Controllers: [{ Type: "Keypad", Actions: {} }],
				Icon: "",
				Name: "",
			});
			if (device === "plus") {
				for (const [index, page] of PLUS_PAGES.entries()) {
					const actions = {};
					const putNavigation = (target, position) => {
						const settings = { page: index, target };
						const feedback = navigationFeedback(settings, index);
						const coordinate = `${position % 4},${Math.floor(position / 4)}`;
						actions[coordinate] = key(
							`${device}/${page.id}/${coordinate}`,
							"Plus navigation",
							`${uuid}.plus-navigation`,
							settings,
						);
						actions[coordinate].State = feedback.selected ? 1 : 0;
						// Native custom images/titles override SDK feedback, so leave both plugin-owned.
						actions[coordinate].States = [0, 1].map(() => ({
							FontSize: 10,
							TitleAlignment: "bottom",
							ShowTitle: true,
						}));
					};
					["library", "playback", "curves", "markers"].forEach((target, position) => putNavigation(target, position));
					if (page.group === "playback" || page.group === "markers") {
						const first = page.group === "playback" ? 1 : 4;
						putNavigation(first, 5);
						putNavigation(first + 1, 6);
					}
					const controls =
						page.group === "library"
							? ["library.open.same", "library.open.new", "library.import", "library.filter.reset"]
							: page.group === "curves"
								? ["first", "second", "third", "calibrated"].map((curve) => control("curve.set", { curve }))
								: ["playback.toggle"];
					controls.forEach((definition, offset) => {
						const coordinate = `${offset},1`;
						actions[coordinate] = key(
							`${device}/${page.id}/${coordinate}`,
							"Analyzer control",
							`${uuid}.control`,
							typeof definition === "string" ? control(definition) : definition,
						);
						actions[coordinate].States = [0, 1].map(() => ({
							FontSize: 10,
							TitleAlignment: "bottom",
							ShowTitle: true,
						}));
					});
					if (page.group === "playback" || page.group === "markers") {
						actions["3,1"] = key(`${device}/${page.id}/mode`, "Step size", `${uuid}.step-mode`, {});
						actions["3,1"].States = [0, 1, 2].map(() => ({ FontSize: 10, TitleAlignment: "bottom", ShowTitle: true }));
					}
					let dials;
					if (page.id === "library") {
						dials = [
							{ control: "library" },
							{ control: "display" },
							{ control: "filter", filter: "park" },
							{ control: "filter", filter: "status" },
						];
					} else if (page.id === "selection") {
						dials = [
							...["start", "end"].map((boundary) => ({ control: "selection", boundary })),
							{ control: "view" },
							{ control: "zoom_selection" },
						];
					} else if (page.id === "curves") {
						dials = ["smoothing", "combined", "view", "position"].map((control) => ({ control }));
					} else if (page.id === "markers") {
						dials = ["start", "gravity", "incline", "end"].map((marker) => ({ control: "marker", marker }));
					} else {
						dials = ["position", "speed", "view", "zoom_selection"].map((control) => ({ control }));
					}
					await add(`Profiles/${pageId(page.id).toUpperCase()}/manifest.json`, {
						Controllers: [
							{ Type: "Keypad", Actions: actions },
							{
								Type: "Encoder",
								Actions: Object.fromEntries(
									dials.map((settings, column) => [
										`${column},0`,
										key(`${device}/${page.id}/dial/${column}`, "Analyzer dial", `${uuid}.dial`, {
											...settings,
											menu: page.group,
											column,
										}),
									]),
								),
							},
						],
						Icon: "",
						Name: page.name,
					});
				}
				await writeFile(
					path.join(plugin, `profiles/plus${language === "en" ? "" : `-${language}`}.streamDeckProfile`),
					await writer.close(),
				);
				continue;
			}
			for (const [name, page] of Object.entries(device === "mobile" ? mobilePages : pages)) {
				if (device === "neo" && name === "selection") continue;
				const actions = {};
				const images = new Map();
				const put = (definition, index) => {
					const coordinate = `${index % columns},${Math.floor(index / columns)}`;
					const id = `${device}/${name}/${coordinate}`;
					if (definition.page) {
						actions[coordinate] = key(
							id,
							"Create Folder",
							"com.elgato.streamdeck.profile.openchild",
							{ ProfileUUID: pageId(definition.page) },
							definition.page === "view" && device !== "mobile" ? "Curves" : definition.title,
						);
						const symbol = definition.page.startsWith("marker.")
							? definition.page.slice(7)
							: definition.page === "view"
								? device === "mobile"
									? "view"
									: "combined"
								: definition.page;
						const image = `Images/${definition.page}.svg`;
						actions[coordinate].States[0].Image = image;
						images.set(image, keyImage(symbol, undefined));
					} else {
						actions[coordinate] = key(id, "Analyzer control", `${uuid}.control`, definition);
						actions[coordinate].States = [0, 1].map(() => ({
							FontSize: 10,
							TitleAlignment: "bottom",
							ShowTitle: true,
						}));
					}
				};
				const marker = name.startsWith("marker.") ? name.slice(7) : undefined;
				const keys = marker
					? [-10, -1, 1, 10].map((steps) => control("marker.preview", { marker, steps }))
					: device === "neo" && name === "explorer"
						? page.keys.filter((key) => key.page !== "selection")
						: page.keys;
				let positions;
				if (device === "mobile") {
					positions = { start: [1, 2], library: [1, 2, 4, 3, 5], playback: [1, 2, 3, 4, 5], view: [1, 2, 3, 4, 5] }[
						name
					];
				} else if (marker) {
					positions = [1, 5, 6, 2];
				} else {
					positions = {
						start: [1, 2],
						explorer: [1, 2, 5],
						library: [1, 2, 5, 4, 6],
						playback: [1, 5, 2, 6],
						position: [1, 5, 6, 2],
						smoothing: [5, 2, 6],
						speed: [5, 2, 6],
						markers: [1, 2, 5, 6],
						view: [1, 2, 3, 6],
					}[name];
				}
				keys.forEach((definition, index) =>
					put(definition, positions?.[index] ?? (name === "start" ? index : index + 1)),
				);
				if (name === "start") {
					actions["0,0"] = key(
						`${device}/${name}/launch`,
						"Open",
						"com.elgato.streamdeck.system.open",
						{ path: "" },
						"Start app",
					);
					const image = "Images/application.png";
					actions["0,0"].States[0].Image = image;
					await writer.add(
						`${root}/Profiles/${pageId(name).toUpperCase()}/${image}`,
						new Uint8ArrayReader(await readFile(path.join(plugin, "imgs/plugin@2x.png"))),
					);
					const websitePosition = device === "mobile" ? "0,1" : "3,0";
					actions[websitePosition] = key(
						`${device}/${name}/website`,
						"Website",
						"com.elgato.streamdeck.system.website",
						{ path: metadata.URL, openInBrowser: true },
						"Website",
					);
					const websiteImage = "Images/website.svg";
					actions[websitePosition].States[0].Image = websiteImage;
					images.set(websiteImage, keyImage("website", undefined));
				}
				const extra =
					device === "mobile"
						? []
						: marker
							? [control("marker.discard", { marker }), control("marker.apply", { marker })]
							: (page.extra ?? []);
				if (!(device === "neo" && name === "position"))
					extra.forEach((definition, index) =>
						put(
							definition,
							device === "neo" && marker
								? [4, 3][index]
								: name === "view" && (device === "neo" || index === 0)
									? index + 4
									: index + 5,
						),
					);
				if (name !== "start") {
					// Stream Deck forces native folder Back to key 1 during import.
					actions["0,0"] = key(
						`${device}/${name}/back`,
						"Parent Folder",
						"com.elgato.streamdeck.profile.backtoparent",
						{},
						"Back",
					);
					if (device === "neo")
						actions[homePosition] = key(`${device}/${name}/home`, "Home", `${uuid}.home`, {}, "Home");
					for (const [position, symbol] of [["0,0", "back"], ...(device === "neo" ? [[homePosition, "home"]] : [])]) {
						const image = `Images/${symbol}.svg`;
						actions[position].States[0].Image = image;
						images.set(image, keyImage(symbol, undefined));
					}
				}
				if (device === "neo" && name === "quick") actions["0,0"].UUID = `${uuid}.home`;
				const controllers = [{ Type: "Keypad", Actions: actions }];
				if (device === "neo") {
					controllers.push({
						Type: "Neo",
						Actions: {
							"1,0": key(`${device}/${name}/info`, "Analyzer InfoBar", `${uuid}.infobar`, {
								section: marker ? "markers" : name === "quick" ? "playback" : name,
								...(marker ? { marker } : {}),
							}),
						},
					});
				}
				await add(`Profiles/${pageId(name).toUpperCase()}/manifest.json`, {
					Controllers: controllers,
					Icon: "",
					Name: page.name,
				});
				for (const [image, svg] of images) {
					await writer.add(`${root}/Profiles/${pageId(name).toUpperCase()}/${image}`, new TextReader(svg));
				}
			}
			await writeFile(
				path.join(plugin, `profiles/${device}${language === "en" ? "" : `-${language}`}.streamDeckProfile`),
				await writer.close(),
			);
		}
	}
	setLanguage("en");
	profileLanguage = "en";
	console.log("Built Plus native pages and Neo/Mobile native folder profiles.");
}
