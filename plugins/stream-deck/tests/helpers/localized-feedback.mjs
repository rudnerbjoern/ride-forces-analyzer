/** Export fresh production feedback for the native Windows font and rendering test. */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { CONTROL_LABELS, controlSettings } from "../../dist/controls.js";
import { infoFeedback } from "../../dist/device-feedback.js";
import { keyFeedback } from "../../dist/feedback.js";
import { LANGUAGES, setLanguage } from "../../dist/localization.js";
import { plusFeedback } from "../../dist/plus-feedback.js";

const fixture = JSON.parse(
	await readFile(new URL("../../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
).messages[0];
const client = () => ({
	state: structuredClone(fixture),
	status: "connected",
	pending: () => false,
	error: () => undefined,
});
const surfaces = [];
const keys = [];
const neo = [];
for (const language of LANGUAGES) {
	setLanguage(language);
	for (const operation of Object.keys(CONTROL_LABELS))
		keys.push({ language, operation, ...keyFeedback(client(), "example", controlSettings({ operation })) });
	for (const section of ["start", "library", "explorer", "playback", "view", "smoothing", "speed", "markers"])
		neo.push({ language, section, feedback: infoFeedback(client(), { section }) });
	for (const control of [
		"library",
		"position",
		"view",
		"smoothing",
		"speed",
		"combined",
		"playback",
		"zoom_selection",
		"selection",
		"marker",
		"filter",
	]) {
		const settings = { control, marker: "gravity", boundary: "end", filter: "status" };
		const h = client();
		for (const status of ["connected", "disconnected"]) {
			h.status = status;
			surfaces.push({ language, control, connection: status, feedback: plusFeedback(h, "example", settings, 20) });
		}
	}
}
setLanguage("en");
const directory = fileURLToPath(new URL("../../../../.tmp/stream-deck-localization/", import.meta.url));
await mkdir(directory, { recursive: true });
await writeFile(path.join(directory, "surfaces.json"), JSON.stringify({ surfaces, keys, neo }, null, 2) + "\n");
