import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { changedPaths, classifyChanges, writeOutputs } from "../../.github/scripts/ci-changes.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));

for (const filename of ["README.md", "AGENTS.md", "docs/nested/PLAN.md",
  ".github/commit-message-instructions.md", "src/package/README.md", "tests/NOTES.md"]) {
  test(`Markdown only selects documentation: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), { code: false, documentation: true });
  });
}

for (const filename of ["src/ride_forces_analyzer/importers/service.py", "tests/test_decoder.py",
  "tests/types/recording.test.mjs", "tests/docs/documentation.test.mjs",
  "tests/fixtures/schema-inventory.json", "tests/fixtures/real/recording.forces",
  "pyproject.toml", "uv.lock", ".python-version", ".node-version", "package.json",
  "package-lock.json", ".github/workflows/ci.yml", ".github/dependabot.yml", ".github/scripts/ci-changes.mjs",
  ".gitignore", ".gitattributes", ".editorconfig", ".vscode/settings.json", "tools/check.ps1"]) {
  test(`Changed code/test input selects code checks: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), { code: true, documentation: false });
  });
}

for (const filenames of [[], ["docs/diagram.svg"], [".cspell.json", ".markdownlint-cli2.jsonc"]]) {
  test(`Unrelated changes do not select test suites: ${JSON.stringify(filenames)}`, () => {
    assert.deepEqual(classifyChanges(filenames), { code: false, documentation: false });
  });
}

test("Mixed changes select both suites", () => {
  assert.deepEqual(classifyChanges(["docs/API.md", "src/import.py"]),
    { code: true, documentation: true });
});

test("Missing or option-like revisions fail instead of silently skipping tests", () => {
  for (const revision of [undefined, "", "HEAD", "--output=file", "a".repeat(39)]) {
    assert.throws(() => changedPaths(revision, "a".repeat(40)), /full commit SHA/);
    assert.throws(() => changedPaths("a".repeat(40), revision), /full commit SHA/);
  }
  assert.throws(() => writeOutputs({ code: false, documentation: false }), /GITHUB_OUTPUT/);
});

test("Real PR diffs cover renames, deletions, divergent base and cumulative changes", async () => {
  await mkdir(path.join(root, ".tmp"), { recursive: true });
  const directory = await mkdtemp(path.join(root, ".tmp/ci-changes-"));
  function git(...args) {
    const result = spawnSync("git", args, { cwd: directory, encoding: "utf8", timeout: 30000 });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    return result.stdout.trim();
  }
  async function put(filename, contents) {
    await mkdir(path.dirname(path.join(directory, filename)), { recursive: true });
    await writeFile(path.join(directory, filename), contents);
  }
  function commit(message) {
    git("add", "--all");
    git("commit", "-m", message);
    return git("rev-parse", "HEAD");
  }
  try {
    git("init", "--initial-branch=base");
    git("config", "user.name", "CI Test");
    git("config", "user.email", "ci-test@example.invalid");
    git("config", "core.autocrlf", "false");
    await put("src/old.py", "value = 1\n");
    await put("docs/deleted.md", "# Original\n");
    const base = commit("Synthetic base");
    git("switch", "-c", "feature");
    await rename(path.join(directory, "src/old.py"), path.join(directory, "docs/renamed.md"));
    await rm(path.join(directory, "docs/deleted.md"));
    const head = commit("Synthetic rename and deletion");
    assert.deepEqual(changedPaths(base, head, directory).sort(),
      ["docs/deleted.md", "docs/renamed.md", "src/old.py"]);
    assert.deepEqual(classifyChanges(changedPaths(base, head, directory)),
      { code: true, documentation: true });
    await put("docs/final notes.md", "# Final notes\n");
    const finalHead = commit("Synthetic documentation update");
    // A docs-only last commit must not hide earlier unmerged code changes.
    assert.deepEqual(classifyChanges(changedPaths(base, finalHead, directory)),
      { code: true, documentation: true });
    git("switch", "base");
    await put("src/base_only.py", "value = 2\n");
    const divergentBase = commit("Synthetic base-only change");
    assert.ok(!changedPaths(divergentBase, finalHead, directory).includes("src/base_only.py"));
    assert.throws(() => changedPaths("f".repeat(40), finalHead, directory), /Cannot determine/);
    const output = path.join(directory, "output.txt");
    await writeFile(output, "existing=true\n");
    writeOutputs({ code: true, documentation: false }, output);
    assert.equal(await readFile(output, "utf8"),
      "existing=true\ncode=true\ndocumentation=false\n");
    const cli = spawnSync(process.execPath, [path.join(root, ".github/scripts/ci-changes.mjs")], {
      cwd: directory,
      encoding: "utf8",
      timeout: 30000,
      env: { ...process.env, PR_BASE_SHA: divergentBase, PR_HEAD_SHA: finalHead,
        GITHUB_OUTPUT: output },
    });
    assert.ifError(cli.error);
    assert.equal(cli.status, 0, cli.stdout + cli.stderr);
    assert.match(cli.stdout, /Code checks: true; documentation checks: true/);
    assert.ok((await readFile(output, "utf8")).endsWith("code=true\ndocumentation=true\n"));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("The actual workflow gate rejects failed, cancelled, missing and inconsistent results", async () => {
  const workflow = await readFile(path.join(root, ".github/workflows/ci.yml"), "utf8");
  const body = workflow.match(/        run: \|\r?\n((?:          .*\r?\n)+)/)?.[1];
  assert.ok(body, "Missing final workflow gate script");
  const cases = [
    ["success", "true", "true", "success", "success", true],
    ["success", "true", "false", "success", "skipped", true],
    ["success", "false", "true", "skipped", "success", true],
    ["success", "false", "false", "skipped", "skipped", true],
    ["failure", "false", "false", "skipped", "skipped", false],
    ["cancelled", "false", "false", "skipped", "skipped", false],
    ["success", "", "true", "skipped", "success", false],
    ["success", "false", "invalid", "skipped", "skipped", false],
    ["success", "true", "false", "failure", "skipped", false],
    ["success", "false", "true", "skipped", "failure", false],
    ["success", "true", "false", "cancelled", "skipped", false],
    ["success", "true", "false", "skipped", "skipped", false],
    ["success", "false", "true", "success", "success", false],
  ];
  await mkdir(path.join(root, ".tmp"), { recursive: true });
  const directory = await mkdtemp(path.join(root, ".tmp/ci-gate-"));
  try {
    await writeFile(path.join(directory, "gate.ps1"),
      "$ErrorActionPreference = 'Stop'\n" + body.replace(/^ {10}/gm, ""));
    await writeFile(path.join(directory, "cases.json"), JSON.stringify(cases));
    const runner = path.join(directory, "verify.ps1");
    await writeFile(runner, `$ErrorActionPreference = 'Stop'
$cases = Get-Content -Raw (Join-Path $PSScriptRoot 'cases.json') | ConvertFrom-Json
foreach ($case in $cases) {
    $env:DEPENDENCY_RESULT = $case[0]
    $env:CODE_REQUIRED = $case[1]
    $env:DOCUMENTATION_REQUIRED = $case[2]
    $env:CODE_RESULT = $case[3]
    $env:DOCUMENTATION_RESULT = $case[4]
    $passed = $true
    try { & (Join-Path $PSScriptRoot 'gate.ps1') } catch { $passed = $false }
    if ($passed -ne $case[5]) { throw "Unexpected gate outcome: $case" }
}
Write-Output "Verified $($cases.Count) workflow gate cases."
`);
    const result = spawnSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass",
      "-File", runner], { cwd: root, encoding: "utf8", timeout: 30000 });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /Verified 13 workflow gate cases/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
