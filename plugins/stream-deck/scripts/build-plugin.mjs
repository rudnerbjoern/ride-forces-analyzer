import { copyFile, cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { buildProfiles } from "./build-profiles.mjs";
import { pluginOutput as plugin } from "./artifact-path.mjs";

const workspace = fileURLToPath(new URL("../", import.meta.url));
const source = path.join(workspace, "io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin");
const compiled = spawnSync(process.execPath, [path.join(workspace, "../../node_modules/typescript/bin/tsc"),
  "--project", path.join(workspace, "tsconfig.json")], { stdio: "inherit", cwd: workspace });
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
manifest.Actions.push(...devices.Actions);
await writeFile(path.join(plugin, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
await cp(path.join(workspace, "devices/layouts"), path.join(plugin, "layouts"), { recursive: true });
await buildProfiles(plugin);
const result = await build({
  absWorkingDir: workspace, entryPoints: ["src/index.ts"], outfile: path.join(plugin, "bin/plugin.js"),
  bundle: true, platform: "node", target: "node24", format: "esm", metafile: true,
  banner: { js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' },
});
await build({ absWorkingDir: workspace, entryPoints: ["src/inspector.ts"],
  outfile: path.join(plugin, "ui/control.js"), bundle: true, platform: "browser", target: "es2024" });
const packages = new Set();
for (const input of Object.keys(result.metafile.inputs)) {
  if (!input.includes("node_modules/")) continue;
  let directory = path.dirname(path.resolve(workspace, input));
  while (directory !== path.dirname(directory)) {
    try {
      const metadata = JSON.parse(await readFile(path.join(directory, "package.json"), "utf8"));
      if (metadata.name && metadata.version) { packages.add(directory); break; }
    } catch { /* Search upwards for the runtime package owning this input. */ }
    directory = path.dirname(directory);
  }
}
const notices = [];
for (const directory of [...packages].sort()) {
  const metadata = JSON.parse(await readFile(path.join(directory, "package.json"), "utf8"));
  const files = (await readdir(directory)).filter(name => /^license(?:\..*)?$/i.test(name));
  if (!files.length) throw new Error(`Missing runtime license: ${metadata.name}`);
  notices.push(`${metadata.name} ${metadata.version}\n${(await Promise.all(files.map(name => readFile(path.join(directory, name), "utf8")))).join("\n")}`);
}
await copyFile(path.join(workspace, "../../LICENSE"), path.join(plugin, "LICENSE"));
await writeFile(path.join(plugin, "THIRD_PARTY_NOTICES.txt"), notices.join("\n\n---\n\n"));
console.log(`Built self-contained plugin; included licenses for ${packages.size} runtime packages.`);
