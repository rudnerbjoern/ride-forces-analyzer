import { TextWriter, Uint8ArrayReader, ZipReader } from "@zip.js/zip.js";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { CONTROL_LABELS, controlSettings } from "../dist/controls.js";
import { dialFeedback, infoFeedback } from "../dist/device-feedback.js";
import { keyFeedback } from "../dist/feedback.js";
import { getLanguage, LANGUAGES, profilePath, setLanguage, translate } from "../dist/localization.js";
import { navigationFeedback } from "../dist/navigation.js";
import { plusFeedback } from "../dist/plus-feedback.js";
import { pluginOutput } from "../scripts/artifact-path.mjs";

const fixture = JSON.parse(
	await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
).messages[0];
const client = () => ({
	state: structuredClone(fixture),
	status: "connected",
	pending: () => false,
	error: () => undefined,
});

test("regional SDK locales select one supported language and retain familiar English controls", () => {
	for (const [input, expected] of [
		["de-DE", "de"],
		["fr_FR", "fr"],
		["en-GB", "en"],
		["ja", "en"],
	]) {
		setLanguage(input);
		assert.equal(getLanguage(), expected);
		assert.equal(translate("Play/Pause"), "Play/Pause");
		assert.equal(profilePath("neo"), `profiles/neo${expected === "en" ? "" : `-${expected}`}`);
	}
	setLanguage("en");
});

test("key captions remain short across languages, operations and failure/connection states", () => {
	try {
		for (const language of LANGUAGES) {
			setLanguage(language);
			for (const operation of Object.keys(CONTROL_LABELS)) {
				const h = client();
				for (const status of ["connected", "connecting", "incompatible", "disconnected"]) {
					h.status = status;
					const result = keyFeedback(h, "example", controlSettings({ operation }));
					assert.ok(result.title.split("\n").length <= 2);
					for (const line of result.title.split("\n")) assert.ok(line.length <= 11, `${language}: ${line}`);
				}
				h.status = "connected";
				h.error = () => ({ error: "analysis.failed" });
				assert.equal(keyFeedback(h, "example", { operation }).title.split("\n")[1], translate("Failed"));
			}
			assert.equal(navigationFeedback({ page: 0, target: "curves" }, 0).title.split("\n")[0], translate("Curves"));
			assert.equal(navigationFeedback({ page: 2, target: 2 }, 2).title, translate("Selection"));
		}
	} finally {
		setLanguage("en");
	}
});

test("localized surfaces retain recording and custom park names even when they match catalog words", () => {
	try {
		for (const language of ["de", "fr"]) {
			setLanguage(language);
			const h = client();
			h.state.library.selected.title = "Ready · Gravity / Start";
			assert.equal(plusFeedback(h, "library", { control: "library" }, 1).value, "Ready · Gravity / Start");
			h.state.library.park_filter.value = "Park A";
			h.state.library.park_filter.options.find((option) => option.value === "Park A").label = "Gravity";
			const park = plusFeedback(h, "park", { control: "filter", filter: "park" }, 1);
			assert.equal(park.value, "Gravity");
			assert.equal(park.detail, `${translate("Active")}: Gravity`);
			const all = plusFeedback(h, "park", { control: "filter", filter: "park" }, 1, null);
			assert.equal(all.value, translate("All parks"));
			assert.equal(all.hint, translate("Press: Filter · Touch: All"));
			assert.equal(dialFeedback(h, "curve", { control: "smoothing" }, 1).title, translate("Smoothing"));
			assert.ok(infoFeedback(h, { section: "markers" }).value.includes(translate("Gravity")));
		}
	} finally {
		setLanguage("en");
	}
});

test("localized native profiles and manifest resources are complete and have distinct identities", async () => {
	const manifest = JSON.parse(await readFile(path.join(pluginOutput, "manifest.json"), "utf8"));
	assert.equal(manifest.Profiles.length, 9);
	const identities = new Set();
	for (const language of LANGUAGES) {
		const resource = JSON.parse(await readFile(path.join(pluginOutput, `${language}.json`), "utf8"));
		for (const action of manifest.Actions) {
			assert.equal(resource[action.UUID].Name, translate(action.Name, language));
			assert.ok(resource[action.UUID].Tooltip);
		}
		for (const device of ["plus", "neo", "mobile"]) {
			const name = profilePath(device, language);
			assert.ok(manifest.Profiles.some((profile) => profile.Name === name));
			const reader = new ZipReader(
				new Uint8ArrayReader(await readFile(path.join(pluginOutput, `${name}.streamDeckProfile`))),
			);
			try {
				const entries = await reader.getEntries();
				const root = entries[0].filename.split("/")[0];
				assert.ok(!identities.has(root));
				identities.add(root);
				const pages = [];
				for (const entry of entries.filter((item) => /\/Profiles\/[^/]+\/manifest.json$/.test(item.filename)))
					pages.push(JSON.parse(await entry.getData(new TextWriter())));
				assert.ok(pages.some((page) => page.Name === translate("Library", language)));
				for (const page of pages)
					for (const controller of page.Controllers)
						for (const action of Object.values(controller.Actions))
							for (const state of action.States)
								if (state.Title)
									for (const line of state.Title.split("\n")) assert.ok(line.length <= 11, `${name}: ${line}`);
			} finally {
				await reader.close();
			}
		}
	}
});
