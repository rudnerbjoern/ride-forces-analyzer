import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

// Reuse the existing, locked CSpell YAML consumer; add no test dependency.
const project = createRequire(import.meta.url);
const configConsumer = createRequire(project.resolve("cspell-config-lib"));
const { parseDocument } = configConsumer("yaml");
const source = await readFile(new URL("../../.github/dependabot.yml", import.meta.url), "utf8");
const document = parseDocument(source, { uniqueKeys: true });
assert.deepEqual(document.errors, [], "Dependabot YAML must parse without duplicate keys or errors");
const config = document.toJS();

test("Dependabot covers the native uv, npm and Actions manifests exactly once", () => {
  assert.equal(config.version, 2);
  assert.deepEqual(config.updates.map(update => update["package-ecosystem"]).sort(),
    ["github-actions", "npm", "uv"]);
  for (const update of config.updates) {
    assert.equal(update.directory, "/");
    // Default-branch targeting also preserves security-update customizations.
    assert.ok(!Object.hasOwn(update, "target-branch"));
    assert.ok(!Object.hasOwn(update, "ignore"), "Do not suppress majors or security fixes");
    assert.ok(!Object.hasOwn(update, "registries"));
    assert.ok(!Object.hasOwn(update, "insecure-external-code-execution"));
  }
});

for (const update of config.updates) {
  const ecosystem = update["package-ecosystem"];
  test(`${ecosystem} limits scheduled PR volume without blocking security fixes`, () => {
    assert.equal(update.schedule.interval, "weekly");
    assert.equal(update.schedule.day, "monday");
    assert.equal(update.schedule.timezone, "Europe/Berlin");
    assert.match(update.schedule.time, /^08:(00|15|30)$/);
    assert.equal(update["open-pull-requests-limit"], 3);
    assert.equal(update.cooldown["default-days"], 7);
    assert.ok(!Object.hasOwn(update, "rebase-strategy"), "Keep conflict rebasing enabled");
    const groups = Object.values(update.groups);
    const versions = groups.filter(group => group["applies-to"] === "version-updates");
    const security = groups.filter(group => group["applies-to"] === "security-updates");
    assert.equal(versions.length, 1);
    assert.deepEqual(versions[0].patterns, ["*"]);
    assert.deepEqual(versions[0]["update-types"].sort(), ["minor", "patch"]);
    assert.equal(security.length, 1);
    assert.deepEqual(security[0].patterns, ["*"]);
    assert.ok(!Object.hasOwn(security[0], "update-types"),
      "Security fixes may require a major version");
  });
}

test("Schedules are staggered and version strategies retain usable constraints", () => {
  assert.equal(new Set(config.updates.map(update => update.schedule.time)).size, 3);
  for (const update of config.updates) {
    if (update["package-ecosystem"] === "github-actions") {
      assert.ok(!Object.hasOwn(update, "versioning-strategy"));
    } else {
      assert.equal(update["versioning-strategy"], "increase-if-necessary");
    }
    const prefix = update["commit-message"].prefix;
    assert.ok(prefix.length <= 50);
    assert.match(prefix, /^:(package|gear): (build\(deps\)|ci\(ci\)) $/);
    assert.ok(!Object.hasOwn(update["commit-message"], "include"),
      "Do not add a second generated dependency scope");
  }
});

test("Dependabot PRs use the existing read-only PR CI, with no automatic merge workflow", async () => {
  const workflowSource = await readFile(new URL("../../.github/workflows/ci.yml", import.meta.url), "utf8");
  const workflow = parseDocument(workflowSource).toJS();
  assert.deepEqual(Object.keys(workflow.on), ["pull_request"]);
  assert.deepEqual(workflow.permissions, { contents: "read" });
  assert.ok(!/pull_request_target|--auto|enable_auto_merge|merge_pull_request/.test(workflowSource));
  const manifests = JSON.parse(await readFile(new URL("../../package.json", import.meta.url), "utf8"));
  // Keep patched override floors while allowing newer stable proposals.
  for (const [value, minimum] of [
    [manifests.overrides?.["smol-toml"], [1, 9, 0]],
    [manifests.overrides?.["micromark-extension-math"]?.katex, [0, 18, 2]],
  ]) {
    assert.equal(typeof value, "string", "Reviewed security override is missing");
    assert.match(value, /^\d+\.\d+\.\d+$/, "Override must pin a stable release");
    const version = value.split(".").map(Number);
    const firstDifference = version.findIndex((part, index) => part !== minimum[index]);
    assert.ok(firstDifference === -1 || version[firstDifference] > minimum[firstDifference],
      "Override falls below the vendor's patched version");
  }
});
