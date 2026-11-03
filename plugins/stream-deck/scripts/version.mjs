import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const packagePath = "plugins/stream-deck/package.json";
const manifestPath = "plugins/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/manifest.json";
const inputs = ["plugins/stream-deck", "package.json", "package-lock.json", ".node-version", "LICENSE",
  ":(exclude)plugins/stream-deck/tests", ":(glob,exclude)plugins/stream-deck/**/*.md"];
const json = filename => JSON.parse(readFileSync(filename, "utf8"));

/** Convert the independent package version to Elgato's four numeric components. */
export function nativeVersion(version) {
  if (!/^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/.test(version)
      || version.split(".").some(part => Number(part) > 65535)) throw new Error("Plugin version must be three numeric components from 0 to 65535");
  return `${version}.0`;
}

/** Synchronize the source manifest after npm version updates the workspace package. */
export function syncVersion(directory = root) {
  const manifest = json(path.join(directory, manifestPath));
  manifest.Version = nativeVersion(json(path.join(directory, packagePath)).version);
  writeFileSync(path.join(directory, manifestPath), JSON.stringify(manifest, null, 2) + "\n");
}

/** Keep a development version stable and require an increase over the last release. */
export function verifyVersion(directory = root) {
  const git = (...args) => execFileSync("git", args, { cwd: directory, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  const version = json(path.join(directory, packagePath)).version;
  const native = nativeVersion(version);
  if (json(path.join(directory, manifestPath)).Version !== native) throw new Error("Plugin manifest version is out of sync; run the workspace npm version command");
  if (json(path.join(directory, "package-lock.json")).packages["plugins/stream-deck"].version !== version) throw new Error("Plugin package-lock version is out of sync");
  if (git("rev-parse", "--is-shallow-repository") === "true") throw new Error("Plugin version checks require full Git history (fetch-depth: 0)");
  const dirty = git("diff", "--name-only", "HEAD", "--", ...inputs)
    || git("ls-files", "--others", "--exclude-standard", "--", ...inputs);
  const releaseTag = tag => /^v\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$/.test(tag);
  const tagged = git("tag", "--points-at", "HEAD", "--list", "v[0-9]*").split("\n").some(releaseTag);
  // A clean tagged candidate must still be checked against the preceding release.
  const reference = tagged && !dirty ? git("rev-list", "--parents", "-n", "1", "HEAD").split(" ")[1] : "HEAD";
  if (!reference) return native;
  const releases = git("tag", "--merged", reference, "--list", "v[0-9]*").split("\n").filter(releaseTag);
  if (!releases.length) return native;
  const release = git("describe", "--tags", "--abbrev=0", ...releases.flatMap(tag => ["--match", tag]), reference);
  const files = git("ls-tree", "--name-only", release, "--", packagePath);
  if (!files) return native; // Initial plugin addition has no earlier version.
  const changed = git("diff", "--name-only", release, "--", ...inputs)
    || git("ls-files", "--others", "--exclude-standard", "--", ...inputs);
  if (!changed) return native;
  const previous = JSON.parse(git("show", `${release}:${packagePath}`)).version;
  const currentParts = nativeVersion(version).split(".").map(Number);
  const previousParts = nativeVersion(previous).split(".").map(Number);
  const difference = currentParts.findIndex((part, index) => part !== previousParts[index]);
  if (difference < 0 || currentParts[difference] < previousParts[difference]) {
    throw new Error(`Plugin code/data changed since release ${release} without a version increase (${previous} -> ${version}); run npm version patch --workspace plugins/stream-deck --no-git-tag-version`);
  }
  return native;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv[2] === "--sync") syncVersion();
  else console.log(`Plugin version verified: ${verifyVersion()}`);
}
