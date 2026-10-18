import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
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

test("Changed workflow validation is checksum-pinned and required by the final gate", async () => {
  const source = await readFile(new URL("../../.github/workflows/ci.yml", import.meta.url), "utf8");
  const workflow = parseDocument(source).toJS();
  const lint = workflow.jobs.actionlint;
  assert.equal(lint.needs, "dependency-check");
  assert.equal(lint.if, "${{ needs.dependency-check.outputs.workflows == 'true' }}");
  assert.equal(lint["timeout-minutes"], 10);
  assert.deepEqual(lint.steps[0].with, { "persist-credentials": false, ref: "${{ github.sha }}" });
  const install = lint.steps.find(step => step.name === "Install checksum-pinned actionlint").run;
  assert.match(install, /actionlint_1\.7\.12_windows_amd64\.zip/);
  assert.match(install, /6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9/);
  assert.match(install, /Get-FileHash.*SHA256/);
  assert.match(install, /--retry 3 --retry-all-errors --connect-timeout 30 --max-time 120/);
  assert.doesNotMatch(install, /--insecure|--ssl-no-revoke|--ssl-revoke-best-effort/);
  assert.ok(workflow.jobs.check.needs.includes("actionlint"));
  const env = workflow.jobs.check.steps[0].env;
  assert.equal(env.WORKFLOWS_REQUIRED, "${{ needs.dependency-check.outputs.workflows }}");
  assert.equal(env.WORKFLOWS_RESULT, "${{ needs.actionlint.result }}");
});

test("Secret scanning is mandatory, checksum-pinned and cannot silently skip the merge gate", async () => {
  const source = await readFile(new URL("../../.github/workflows/ci.yml", import.meta.url), "utf8");
  const workflow = parseDocument(source).toJS();
  const scan = workflow.jobs.gitleaks;
  assert.equal(scan["runs-on"], "windows-latest");
  assert.equal(scan["timeout-minutes"], 10);
  assert.ok(!Object.hasOwn(scan, "if") && !Object.hasOwn(scan, "needs"));
  assert.ok(!Object.hasOwn(scan, "continue-on-error"));
  assert.deepEqual(scan.steps[0].with, { "persist-credentials": false, "fetch-depth": 0, ref: "${{ github.sha }}" });
  const install = scan.steps.find(step => step.name === "Install checksum-pinned Gitleaks").run;
  assert.match(install, /gitleaks_8\.30\.1_windows_x64\.zip/);
  assert.match(install, /d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e/);
  assert.match(install, /Get-FileHash.*SHA256/);
  assert.match(install, /useDefault = true/);
  assert.match(install, /--retry 3 --retry-all-errors --connect-timeout 30 --max-time 120/);
  assert.doesNotMatch(install, /--insecure|--ssl-no-revoke|--ssl-revoke-best-effort/);
  assert.ok(scan.steps.some(step => step.run === "./.github/scripts/test-gitleaks.ps1"));
  const command = scan.steps.find(step => step.name === "Scan complete fetched Git history").run;
  for (const flag of ["--log-opts=--all", "--ignore-gitleaks-allow", "--redact=100", "--exit-code 1",
    "--config=.tmp/gitleaks/rules.toml", "--gitleaks-ignore-path=.tmp/gitleaks/empty-ignore"]) {
    assert.ok(command.includes(flag), flag);
  }
  assert.ok(!scan.steps.some(step => step.uses?.startsWith("actions/upload-artifact@")));
  assert.ok(workflow.jobs.check.needs.includes("gitleaks"));
  assert.equal(workflow.jobs.check.steps[0].env.GITLEAKS_RESULT, "${{ needs.gitleaks.result }}");
});

test("Source releases publish only reviewed tag revisions after quality and package checks", async () => {
  const source = await readFile(new URL("../../.github/workflows/source-release.yml", import.meta.url), "utf8");
  const workflow = parseDocument(source).toJS();
  assert.deepEqual(workflow.on, { push: { tags: ["v*"] } });
  assert.deepEqual(workflow.permissions, { contents: "read" });
  assert.equal(workflow.concurrency["cancel-in-progress"], false);
  assert.equal(workflow.jobs.source["timeout-minutes"], 10);
  assert.deepEqual(workflow.jobs.quality, { uses: "./.github/workflows/ci.yml", with: { "full-checks": true } });
  assert.equal(workflow.jobs.source.needs, "quality");
  assert.equal(workflow.jobs.source.steps[0].with.ref, "${{ github.sha }}");
  assert.ok(!Object.hasOwn(workflow.jobs.source, "if"), "Do not bypass failed quality jobs");
  assert.match(source, /check-source-release\.py/);
  assert.match(source, /uv build --out-dir/);
  const uploads = workflow.jobs.source.steps.filter(step => step.uses?.startsWith("actions/upload-artifact@"));
  assert.deepEqual(uploads.map(step => step.with.path), [".tmp/release/source.zip", ".tmp/release/SHA256SUMS.txt", ".tmp/release/release-notes.md"]);
  for (const upload of uploads) {
    assert.equal(upload.with.archive, false);
    assert.equal(upload.with["retention-days"], 14);
    assert.equal(upload.with["if-no-files-found"], "error");
  }
  const release = workflow.jobs.release;
  assert.deepEqual(release.needs, ["quality", "source", "windows"]);
  assert.equal(release.if, "${{ github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') }}");
  assert.deepEqual(release.permissions, { contents: "write", actions: "read" });
  assert.equal(release["timeout-minutes"], 10);
  assert.equal(workflow.jobs.source.steps[0].with["fetch-depth"], 0);
  assert.match(source, /check-release-policy\.py/);
  const downloads = release.steps.filter(step => step.uses?.startsWith("actions/download-artifact@"));
  assert.deepEqual(downloads.map(step => step.with.name), ["source.zip", "SHA256SUMS.txt", "release-notes.md",
    "${{ needs.windows.outputs.exe }}", "${{ needs.windows.outputs.standard }}", "${{ needs.windows.outputs.complete }}",
    "WINDOWS-SHA256SUMS.txt", "corresponding-sources.zip"]);
  const windows = workflow.jobs.windows;
  assert.deepEqual(windows.needs, ["quality", "source"]);
  assert.equal(windows["timeout-minutes"], 30);
  assert.equal(windows.steps[0].with.ref, "${{ github.sha }}");
  assert.match(windows.steps.find(step => step.id === "build").run, /scripts\.build_windows --release/);
  assert.ok(windows.steps.some(step => step.run?.includes("scripts.check_windows_packages")));
  assert.ok(!windows.permissions?.contents || windows.permissions.contents === "read");
  assert.ok(downloads.every(step => !step.with["run-id"] && !step.with["github-token"]));
  const publication = release.steps.find(step => step.name === "Publish GitHub Release").run;
  assert.match(publication, /'--verify-tag'/);
  assert.match(publication, /'--generate-notes'/);
  assert.match(publication, /'--prerelease'/);
  assert.ok(!/gh release edit|git push|--clobber/.test(source));
});

test("Actual publication command preserves preview flags and rejects failed release creation", async () => {
  const source = await readFile(new URL("../../.github/workflows/source-release.yml", import.meta.url), "utf8");
  const workflow = parseDocument(source).toJS();
  const body = workflow.jobs.release.steps.find(step => step.name === "Publish GitHub Release").run;
  await mkdir(".tmp", { recursive: true });
  const directory = await mkdtemp(path.resolve(".tmp/release-command-"));
  const script = path.join(directory, "publication.ps1");
  try {
    await writeFile(script, `$ErrorActionPreference = 'Stop'
function gh {
    $global:recorded = @($args)
    $global:LASTEXITCODE = [int]$env:FAKE_EXIT
}
${body}
ConvertTo-Json -Compress -InputObject $global:recorded
`);
    for (const [preview, exit] of [["true", 0], ["false", 0], ["true", 1]]) {
      const result = spawnSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script], {
        encoding: "utf8", timeout: 30000,
        env: { ...process.env, RELEASE_TAG: "v0.1.0", RELEASE_SHA: "a".repeat(40),
          RELEASE_PREVIEW: preview, FAKE_EXIT: String(exit), WINDOWS_EXE: "app.exe",
          WINDOWS_STANDARD: "standard.zip", WINDOWS_COMPLETE: "complete.zip" },
      });
      assert.ifError(result.error);
      if (exit) {
        assert.notEqual(result.status, 0, "Failed publication must fail the workflow");
        continue;
      }
      assert.equal(result.status, 0, result.stderr);
      const args = JSON.parse(result.stdout.trim());
      assert.deepEqual(args.slice(0, 5), ["release", "create", "v0.1.0", ".tmp/release/source.zip", ".tmp/release/SHA256SUMS.txt"]);
      assert.ok(args.includes("--verify-tag") && args.includes("--generate-notes"));
      for (const asset of ["app.exe", "standard.zip", "complete.zip", "WINDOWS-SHA256SUMS.txt", "corresponding-sources.zip"]) {
        assert.ok(args.includes(`.tmp/release/${asset}`));
      }
      assert.equal(args.includes("--prerelease"), preview === "true");
      assert.equal(args.includes("--latest=false"), preview === "true");
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("Actual release artifact verifier rejects a modified Windows download", async () => {
  const workflow = parseDocument(await readFile(new URL("../../.github/workflows/source-release.yml", import.meta.url), "utf8")).toJS();
  const body = workflow.jobs.release.steps.find(step => step.name === "Verify artifacts and current tag before publication").run;
  const directory = await mkdtemp(path.resolve(".tmp/windows-release-verifier-"));
  const target = path.join(directory, ".tmp/release");
  const hash = data => createHash("sha256").update(data).digest("hex");
  try {
    await mkdir(target, { recursive: true });
    await writeFile(path.join(target, "source.zip"), "synthetic source");
    await writeFile(path.join(target, "SHA256SUMS.txt"), `${hash("synthetic source")}  source.zip\n`);
    const names = ["app.exe", "standard.zip", "complete.zip", "corresponding-sources.zip"];
    for (const name of names) await writeFile(path.join(target, name), "synthetic binary");
    await writeFile(path.join(target, "WINDOWS-SHA256SUMS.txt"), names.map(name => `${hash("synthetic binary")}  ${name}\n`).join(""));
    const script = path.join(directory, "verify.ps1");
    await writeFile(script, `$ErrorActionPreference = 'Stop'\nfunction git {\n $global:LASTEXITCODE = 0\n if ($args[0] -eq 'rev-parse') { $env:RELEASE_SHA }\n}\n${body}\nWrite-Output 'Artifact verification passed'\n`);
    const run = () => spawnSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script], {
      cwd: directory, encoding: "utf8", timeout: 30000,
      env: { ...process.env, RELEASE_TAG: "v0.1.0", RELEASE_SHA: "a".repeat(40), RELEASE_PREVIEW: "true",
        WINDOWS_EXE: "app.exe", WINDOWS_STANDARD: "standard.zip", WINDOWS_COMPLETE: "complete.zip" },
    });
    const valid = run();
    assert.ifError(valid.error);
    assert.equal(valid.status, 0, valid.stderr);
    assert.match(valid.stdout, /Artifact verification passed/);
    await writeFile(path.join(target, "app.exe"), "tampered");
    const changed = run();
    assert.ifError(changed.error);
    assert.notEqual(changed.status, 0);
    assert.match(changed.stderr, /Windows artifact checksum mismatch/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("Dependabot PRs use the existing read-only PR CI, with no automatic merge workflow", async () => {
  const workflowSource = await readFile(new URL("../../.github/workflows/ci.yml", import.meta.url), "utf8");
  const workflow = parseDocument(workflowSource).toJS();
  assert.deepEqual(workflow.on, { pull_request: { branches: ["main"] }, workflow_dispatch: null,
    workflow_call: { inputs: { "full-checks": { type: "boolean", required: true } } } });
  for (const job of Object.values(workflow.jobs)) {
    for (const step of job.steps.filter(step => step.uses?.startsWith("actions/checkout@"))) {
      assert.equal(step.with.ref, "${{ github.sha }}");
    }
  }
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
