import { spawnSync } from "node:child_process";
import { cp } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { pluginInstallation, pluginOutput } from "./artifact-path.mjs";

/** Copy a standalone deployment so rebuilding test output cannot modify the installed plugin. */
export async function copyInstallation(source, destination) {
  await cp(source, destination, { recursive: true,
    filter: filename => path.relative(source, filename).split(path.sep)[0] !== "logs" });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  await copyInstallation(pluginOutput, pluginInstallation);
  const require = createRequire(import.meta.url);
  const cli = path.join(path.dirname(require.resolve("@elgato/cli/package.json")), "bin/streamdeck.mjs");
  const linked = spawnSync(process.execPath, [cli, "link", pluginInstallation], { stdio: "inherit" });
  if (linked.error) throw linked.error;
  process.exitCode = linked.status ?? 1;
}
