import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { copyFile, cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { pluginOutput as plugin } from "./artifact-path.mjs";
import { buildProfiles } from "./build-profiles.mjs";
import { verifyVersion } from "./version.mjs";

const workspace = fileURLToPath(new URL("../", import.meta.url));
const source = path.join(workspace, "io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin");
const version = verifyVersion(path.join(workspace, "../.."));
const compiled = spawnSync(
	process.execPath,
	[path.join(workspace, "../../node_modules/typescript/bin/tsc"), "--project", path.join(workspace, "tsconfig.json")],
	{ stdio: "inherit", cwd: workspace },
);
if (compiled.error) throw compiled.error;
if (compiled.status !== 0) process.exit(compiled.status ?? 1);
await rm(plugin, { recursive: true, force: true });
await mkdir(path.join(plugin, "bin"), { recursive: true });
await mkdir(path.join(plugin, "ui"), { recursive: true });
await cp(path.join(source, "imgs"), path.join(plugin, "imgs"), { recursive: true });
await copyFile(path.join(source, "ui/control.html"), path.join(plugin, "ui/control.html"));
await copyFile(path.join(source, "package.json"), path.join(plugin, "package.json"));
const manifest = JSON.parse(await readFile(path.join(source, "manifest.json"), "utf8"));
const devices = JSON.parse(await readFile(path.join(workspace, "devices/manifest.json"), "utf8"));
const { LANGUAGES, TRANSLATIONS, translate } = await import("../dist/localization.js");
manifest.Version = version;
manifest.Actions.push(...devices.Actions);
manifest.Profiles = LANGUAGES.flatMap((language) =>
	manifest.Profiles.map((profile) => ({
		...profile,
		Name: `${profile.Name}${language === "en" ? "" : `-${language}`}`,
	})),
);
await writeFile(path.join(plugin, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
for (const language of LANGUAGES) {
	const resource = {
		Name: manifest.Name,
		Description: translate(manifest.Description, language),
		Localization: Object.fromEntries(Object.keys(TRANSLATIONS).map((key) => [key, translate(key, language)])),
	};
	for (const action of manifest.Actions) {
		const localizedAction = {
			Name: translate(action.Name, language),
			Tooltip: translate(action.Tooltip, language),
		};
		if (action.Encoder?.TriggerDescription)
			localizedAction.Encoder = {
				TriggerDescription: Object.fromEntries(
					Object.entries(action.Encoder.TriggerDescription).map(([key, value]) => [key, translate(value, language)]),
				),
			};
		resource[action.UUID] = localizedAction;
	}
	await writeFile(path.join(plugin, `${language}.json`), JSON.stringify(resource, null, 2) + "\n");
}
await cp(path.join(workspace, "devices/layouts"), path.join(plugin, "layouts"), { recursive: true });
const compact = JSON.parse(await readFile(path.join(plugin, "layouts/plus.json"), "utf8"));
compact.id = "analyzer-plus-compact";
compact.items = compact.items.filter((item) => item.key !== "detail");
compact.items.find((item) => item.key === "hint").rect = [4, 77, 192, 20];
await writeFile(path.join(plugin, "layouts/plus-compact.json"), JSON.stringify(compact, null, 2) + "\n");
await mkdir(path.join(plugin, "layouts/backgrounds"), { recursive: true });
for (const menu of ["library", "playback", "curves", "markers"]) {
	const panorama = (await readFile(path.join(workspace, "devices/backgrounds", `${menu}.svg`), "utf8")).trim();
	for (let column = 0; column < 4; column++) {
		const tile = panorama
			.replace(
				/<svg[^>]*>/,
				`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="${column * 200} 0 200 100">`,
			)
			.replace("</svg>", '<rect width="800" height="100" fill="#080f1b" fill-opacity=".47"/></svg>');
		await writeFile(path.join(plugin, "layouts/backgrounds", `${menu}-${column}.svg`), tile + "\n");
	}
}
await buildProfiles(plugin);
const result = await build({
	absWorkingDir: workspace,
	entryPoints: ["src/index.ts"],
	outfile: path.join(plugin, "bin/plugin.js"),
	bundle: true,
	platform: "node",
	target: "node24",
	format: "esm",
	metafile: true,
	banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({
	absWorkingDir: workspace,
	entryPoints: ["src/inspector.ts"],
	outfile: path.join(plugin, "ui/control.js"),
	bundle: true,
	platform: "browser",
	target: "es2024",
});
const packages = new Set();
for (const input of Object.keys(result.metafile.inputs)) {
	if (!input.includes("node_modules/")) continue;
	let directory = path.dirname(path.resolve(workspace, input));
	while (directory !== path.dirname(directory)) {
		try {
			const metadata = JSON.parse(await readFile(path.join(directory, "package.json"), "utf8"));
			if (metadata.name && metadata.version) {
				packages.add(directory);
				break;
			}
		} catch {
			/* Search upwards for the runtime package owning this input. */
		}
		directory = path.dirname(directory);
	}
}
const notices = [];
for (const directory of [...packages].sort()) {
	const metadata = JSON.parse(await readFile(path.join(directory, "package.json"), "utf8"));
	const files = (await readdir(directory)).filter((name) => /^license(?:\..*)?$/i.test(name));
	if (!files.length) throw new Error(`Missing runtime license: ${metadata.name}`);
	notices.push(
		`${metadata.name} ${metadata.version}\n${(await Promise.all(files.map((name) => readFile(path.join(directory, name), "utf8")))).join("\n")}`,
	);
}
await copyFile(path.join(workspace, "../../LICENSE"), path.join(plugin, "LICENSE"));
await writeFile(path.join(plugin, "THIRD_PARTY_NOTICES.txt"), notices.join("\n\n---\n\n"));
console.log(`Built self-contained plugin; included licenses for ${packages.size} runtime packages.`);
