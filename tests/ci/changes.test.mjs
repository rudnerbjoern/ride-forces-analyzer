import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { changedPaths, classifyChanges, selectChecks, writeOutputs } from "../../.github/scripts/ci-changes.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));

function selected(...names) {
  return Object.fromEntries(["code", "documentation", "skills", "workflows", "dependencies", "posix"]
    .map(name => [name, names.includes(name)]));
}

for (const filename of ["README.md", "AGENTS.md", "docs/nested/PLAN.md",
  ".agents/skills/github-delivery/SKILL.md", "src/package/README.md", "tests/NOTES.md"]) {
  test(`Markdown only selects documentation: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), selected("documentation"));
  });
}

for (const filename of ["src/ride_forces_analyzer/importers/service.py", "tests/importers/test_decoder.py",
  "tests/types/recording.test.mjs", "tests/docs/documentation.test.mjs",
  "tests/fixtures/schema-inventory.json", "tests/fixtures/real/recording.forces",
  ".node-version", "ffmpeg.json", "package.json", "package-lock.json", ".vscode/settings.json", "tools/check.ps1"]) {
  test(`Application/shared tooling input selects application checks: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), selected("code", "dependencies", "posix"));
  });
}

for (const filename of ["pyproject.toml", "uv.lock", ".python-version", ".gitignore", ".gitattributes", ".editorconfig"]) {
  test(`Shared Python/Git input selects application and skill checks: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), selected("code", "dependencies", "posix", "skills"));
  });
}

for (const filename of [".agents/skills/github-delivery/scripts/git_delivery.py",
  ".agents/skills/github-delivery/scripts/git-delivery.ps1", ".agents/skills/github-delivery/tests/test_github_delivery.py"]) {
  test(`Skill implementation/test changes select only skill checks: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), selected("skills"));
  });
}

for (const filename of [".github/labeler.yml", ".github/dependabot.yml", ".github/release.yml",
  ".github/workflows/labeler.yml", ".github/workflows/source-release.yml",
  ".github/scripts/ci-changes.mjs", ".github/scripts/test-gitleaks.ps1",
  "tests/ci/changes.test.mjs", "tests/dependencies/dependabot.test.mjs"]) {
  test(`CI metadata/contracts select targeted checks: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), selected("dependencies", "workflows"));
  });
}

for (const filename of [".github/workflows/posix-packages.yml", ".github/workflows/ci.yml"]) {
  test(`Native/caller workflow selects POSIX independently: ${filename}`, () => {
    assert.deepEqual(classifyChanges([filename]), selected("dependencies", "workflows", "posix"));
  });
}

test("Python release helpers retain conservative application validation", () => {
  assert.deepEqual(classifyChanges([".github/scripts/check-release-policy.py"]),
    selected("code", "dependencies", "workflows", "posix"));
});

test("Mixed labeling and native workflow changes skip application and skill tests", () => {
  assert.deepEqual(classifyChanges([
    ".github/labeler.yml", ".github/workflows/ci.yml", ".github/workflows/posix-packages.yml",
    ".github/workflows/source-release.yml", "docs/development/CI.md", "tests/ci/changes.test.mjs",
    "tests/dependencies/labels.test.mjs", "tests/dependencies/dependabot.test.mjs", ".github/scripts/ci-changes.mjs",
  ]), selected("dependencies", "workflows", "documentation", "posix"));
});

test("The commit policy selects documentation and its consuming skill", () => {
  assert.deepEqual(classifyChanges([".github/commit-message-instructions.md"]), selected("documentation", "skills"));
});

test("Mixed application, documentation and skill changes select all affected suites", () => {
  assert.deepEqual(classifyChanges(["src/import.py", "README.md", ".agents/skills/github-delivery/scripts/git_delivery.py"]),
    selected("code", "documentation", "skills", "dependencies", "posix"));
});

for (const filenames of [[], ["docs/diagram.svg"], [".cspell.json", ".markdownlint-cli2.jsonc"]]) {
  test(`Unrelated changes do not select test suites: ${JSON.stringify(filenames)}`, () => {
    assert.deepEqual(classifyChanges(filenames), selected());
  });
}

test("Mixed application and documentation changes select both", () => {
  assert.deepEqual(classifyChanges(["docs/API.md", "src/import.py"]), selected("code", "documentation", "dependencies", "posix"));
});

test("Manual CI selects every suite without PR revisions; unsupported events fail closed", () => {
  const all = selected("code", "documentation", "skills", "workflows", "dependencies", "posix");
  assert.deepEqual(selectChecks("workflow_dispatch", undefined, undefined, "missing-directory"), all);
  assert.deepEqual(selectChecks("push", undefined, undefined, "missing-directory", true), all);
  for (const event of [undefined, "push", "pull_request_target"]) {
    assert.throws(() => selectChecks(event), /Unsupported CI event/);
  }
  assert.throws(() => selectChecks("pull_request"), /full commit SHA/);
});

test("Missing or option-like revisions fail instead of silently skipping tests", () => {
  for (const revision of [undefined, "", "HEAD", "--output=file", "a".repeat(39)]) {
    assert.throws(() => changedPaths(revision, "a".repeat(40)), /full commit SHA/);
    assert.throws(() => changedPaths("a".repeat(40), revision), /full commit SHA/);
  }
  assert.throws(() => writeOutputs(selected()), /GITHUB_OUTPUT/);
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
      selected("code", "documentation", "dependencies", "posix"));
    await put("docs/final notes.md", "# Final notes\n");
    const finalHead = commit("Synthetic documentation update");
    // A docs-only last commit must not hide earlier unmerged code changes.
    assert.deepEqual(classifyChanges(changedPaths(base, finalHead, directory)),
      selected("code", "documentation", "dependencies", "posix"));
    git("switch", "base");
    await put("src/base_only.py", "value = 2\n");
    const divergentBase = commit("Synthetic base-only change");
    assert.ok(!changedPaths(divergentBase, finalHead, directory).includes("src/base_only.py"));
    assert.throws(() => changedPaths("f".repeat(40), finalHead, directory), /Cannot determine/);
    const output = path.join(directory, "output.txt");
    await writeFile(output, "existing=true\n");
    writeOutputs(selected("code", "skills", "workflows", "dependencies", "posix"), output);
    assert.equal(await readFile(output, "utf8"),
      "existing=true\ncode=true\ndocumentation=false\nskills=true\nworkflows=true\ndependencies=true\nposix=true\n");
    const cli = spawnSync(process.execPath, [path.join(root, ".github/scripts/ci-changes.mjs")], {
      cwd: directory,
      encoding: "utf8",
      timeout: 30000,
      env: { ...process.env, GITHUB_EVENT_NAME: "pull_request", PR_BASE_SHA: divergentBase, PR_HEAD_SHA: finalHead,
        GITHUB_OUTPUT: output },
    });
    assert.ifError(cli.error);
    assert.equal(cli.status, 0, cli.stdout + cli.stderr);
    assert.match(cli.stdout, /Code checks: true; documentation checks: true; skill checks: false/);
    assert.ok((await readFile(output, "utf8")).endsWith("code=true\ndocumentation=true\nskills=false\nworkflows=false\ndependencies=true\nposix=true\n"));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("PR runs cancel only superseded runs of the same workflow and have bounded jobs", async () => {
  const workflow = await readFile(path.join(root, ".github/workflows/ci.yml"), "utf8");
  assert.match(workflow, /group: \$\{\{ github\.workflow \}\}-\$\{\{ github\.event\.pull_request\.number \|\| github\.run_id \}\}/);
  assert.match(workflow, /cancel-in-progress: \$\{\{ github\.event_name == 'pull_request' \}\}/);
  const jobs = workflow.split(/\r?\n(?=  [a-z][a-z-]*:\r?\n)/).slice(1);
  const budgets = { gitleaks: 10, "dependency-check": 5, actionlint: 10, code: 15, ui: 10, skills: 10, documentation: 5, posix: null, check: 5 };
  assert.equal(jobs.length, Object.keys(budgets).length);
  for (const job of jobs) {
    const name = job.match(/^  ([a-z-]+):/)?.[1];
    assert.ok(Object.hasOwn(budgets, name));
    if (name === "posix") {
      assert.match(job, /uses: \.\/\.github\/workflows\/posix-packages\.yml/);
      assert.match(job, /needs\.dependency-check\.outputs\.posix == 'true'/);
      continue;
    }
    assert.match(job, new RegExp(`    timeout-minutes: ${budgets[name]}(?:\\r?\\n)`));
    assert.match(job, /runs-on: windows-latest/);
  }
});

test("Native package uploads require release opt-in while PRs still build and verify", async () => {
  const [ci, packages, release] = await Promise.all([
    readFile(path.join(root, ".github/workflows/ci.yml"), "utf8"),
    readFile(path.join(root, ".github/workflows/posix-packages.yml"), "utf8"),
    readFile(path.join(root, ".github/workflows/source-release.yml"), "utf8"),
  ]);
  for (const workflow of [ci, packages]) {
    assert.match(workflow, /      upload-packages:\r?\n        type: boolean\r?\n        required: false\r?\n        default: false/);
  }
  const caller = ci.split("\n  posix:")[1].split("\n  check:")[0];
  assert.match(caller, /needs\.dependency-check\.outputs\.posix == 'true'/);
  assert.match(caller, /upload-packages: \$\{\{ inputs\.upload-packages \|\| false \}\}/);
  const quality = release.split("\n  quality:")[1].split("\n  source:")[0];
  assert.match(quality, /uses: \.\/\.github\/workflows\/ci\.yml/);
  assert.match(quality, /full-checks: true/);
  assert.match(quality, /upload-packages: true/);
  const steps = packages.split(/\r?\n      - /).slice(1);
  const uploads = steps.filter(step => /uses: actions\/upload-artifact@/.test(step));
  assert.equal(uploads.length, 2, "Release retains both package and checksums");
  for (const upload of uploads) {
    assert.match(upload, /if: \$\{\{ inputs\.upload-packages \}\}/);
    assert.match(upload, /if-no-files-found: error/);
  }
  for (const command of ["scripts.build_posix", "scripts.check_posix_packages"]) {
    const checks = steps.filter(step => step.includes(command));
    assert.ok(checks.length > 0, `Missing native build/verification: ${command}`);
    for (const check of checks) {
      assert.doesNotMatch(check, /inputs\.upload-packages/, "Native validation also runs without uploads");
    }
  }
});

test("Python checks retain locked resolution and bounded reports without hiding test failures", async () => {
  const workflow = await readFile(path.join(root, ".github/workflows/ci.yml"), "utf8");
  const commands = [...workflow.matchAll(/run: (uv run .+)/g)].map(match => match[1]);
  assert.ok(commands.length > 0);
  assert.ok(commands.every(command => command.startsWith("uv run --locked ")));
  assert.doesNotMatch(workflow, /continue-on-error:/);
  for (const [job, report] of [["code", "application"], ["ui", "ui"], ["skills", "skills"]]) {
    const section = workflow.split(`\n  ${job}:`)[1].split(/\n  [a-z-]+:/)[0];
    assert.match(section, /id: pytest/);
    assert.match(section, new RegExp(`pytest .*?-ra --durations=20 --junitxml=\\.tmp/test-results/${report}\\.xml`));
    assert.match(section, /if: \$\{\{ !cancelled\(\) && \(steps\.pytest\.outcome == 'success' \|\| steps\.pytest\.outcome == 'failure'\) \}\}/);
    assert.match(section, new RegExp(`path: \\.tmp/test-results/${report}\\.xml(?:\\r?\\n)`));
    assert.match(section, /if-no-files-found: error/);
    assert.match(section, /include-hidden-files: true/);
    assert.match(section, /retention-days: 14/);
  }
  const code = workflow.split("\n  code:")[1].split(/\n  [a-z-]+:/)[0];
  const ui = workflow.split("\n  ui:")[1].split(/\n  [a-z-]+:/)[0];
  assert.match(code, /pytest --ignore=tests\/ui /);
  assert.match(ui, /pytest tests\/ui /);
  assert.match(ui, /if: \$\{\{ needs\.dependency-check\.outputs\.code == 'true' \}\}/);
  assert.match(workflow, /UI_REQUIRED: \$\{\{ needs\.dependency-check\.outputs\.code \}\}/);
  assert.match(workflow, /UI_RESULT: \$\{\{ needs\.ui\.result \}\}/);
  assert.match(workflow, /POSIX_REQUIRED: \$\{\{ needs\.dependency-check\.outputs\.posix \}\}/);
  assert.match(workflow, /CONTRACTS_REQUIRED: \$\{\{ needs\.dependency-check\.outputs\.dependencies \}\}/);
  assert.match(workflow, /needs: \[dependency-check, code, ui, documentation, skills, gitleaks, actionlint, posix\]/);
});

test("Dependency contracts run in the selector job even when application checks are skipped", async () => {
  const workflow = await readFile(path.join(root, ".github/workflows/ci.yml"), "utf8");
  const dependency = workflow.split("\n  dependency-check:")[1].split("\n  actionlint:")[0];
  assert.match(dependency, /dependencies: \$\{\{ steps\.changes\.outputs\.dependencies \}\}/);
  assert.match(dependency, /posix: \$\{\{ steps\.changes\.outputs\.posix \}\}/);
  for (const command of ["npm ci --no-audit --no-fund", "npm run test:dependencies"]) {
    assert.ok(dependency.includes(`if: \${{ steps.changes.outputs.dependencies == 'true' }}\n        run: ${command}`));
  }
  assert.ok(dependency.indexOf("run: node .github/scripts/ci-changes.mjs") < dependency.indexOf("run: npm run test:dependencies"));
  assert.equal(workflow.match(/run: npm run test:dependencies/g).length, 1);
});

test("The actual workflow gate rejects failed, cancelled, missing and inconsistent results", async () => {
  const workflow = await readFile(path.join(root, ".github/workflows/ci.yml"), "utf8");
  const body = workflow.split("\n  check:")[1].match(/        run: \|\r?\n((?:          .*\r?\n)+)/)?.[1];
  assert.ok(body, "Missing final workflow gate script");
  const cases = [];
  for (const code of ["true", "false"]) {
    for (const documentation of ["true", "false"]) {
      for (const skills of ["true", "false"]) {
        const selections = [code, documentation, skills];
        cases.push(["success", ...selections,
          ...selections.map((required) => required === "true" ? "success" : "skipped"), true]);
      }
    }
  }
  for (const dependency of ["failure", "cancelled"]) {
    cases.push([dependency, "false", "false", "false", "skipped", "skipped", "skipped", false]);
  }
  for (let suite = 0; suite < 3; suite++) {
    for (const invalid of ["", "invalid"]) {
      const example = ["success", "true", "true", "true", "success", "success", "success", false];
      example[1 + suite] = invalid;
      cases.push(example);
    }
    for (const result of ["failure", "cancelled", "skipped", ""]) {
      const example = ["success", "true", "true", "true", "success", "success", "success", false];
      example[4 + suite] = result;
      cases.push(example);
    }
    const inconsistent = ["success", "false", "false", "false", "skipped", "skipped", "skipped", false];
    inconsistent[4 + suite] = "success";
    cases.push(inconsistent);
  }
  for (const example of cases) example.push("success");
  for (const scan of ["failure", "cancelled", "skipped", ""]) {
    cases.push(["success", "false", "false", "false", "skipped", "skipped", "skipped", false, scan]);
  }
  for (const example of cases) example.push("false", "skipped");
  for (const [required, result, passed] of [
    ["true", "success", true], ["true", "failure", false], ["true", "cancelled", false],
    ["true", "skipped", false], ["true", "", false], ["false", "success", false],
    ["", "skipped", false], ["invalid", "skipped", false],
  ]) {
    cases.push(["success", "false", "false", "false", "skipped", "skipped", "skipped", passed, "success", required, result]);
  }
  for (const example of cases) example.push(example[1] === "true" ? "success" : "skipped");
  for (const result of ["failure", "cancelled", "skipped", ""]) {
    cases.push(["success", "true", "false", "false", "success", "skipped", "skipped", false,
      "success", "false", "skipped", result]);
  }
  cases.push(["success", "false", "false", "false", "skipped", "skipped", "skipped", false,
    "success", "false", "skipped", "success"]);
  for (const example of cases) example.push(example[1] === "true" ? "success" : "skipped");
  for (const result of ["failure", "cancelled", "skipped", ""]) {
    cases.push(["success", "true", "false", "false", "success", "skipped", "skipped", false,
      "success", "false", "skipped", "success", result]);
  }
  cases.push(["success", "false", "false", "false", "skipped", "skipped", "skipped", false,
    "success", "false", "skipped", "skipped", "success"]);
  for (const example of cases) example.push(example[1], "false");
  for (const [required, result, passed] of [
    ["true", "success", true], ["true", "failure", false], ["true", "cancelled", false],
    ["true", "skipped", false], ["true", "", false], ["false", "skipped", true],
    ["false", "success", false], ["", "skipped", false], ["invalid", "skipped", false],
  ]) {
    cases.push(["success", "false", "false", "false", "skipped", "skipped", "skipped", passed,
      "success", "false", "skipped", "skipped", result, required, "false"]);
  }
  for (const required of ["", "invalid"]) {
    cases.push(["success", "false", "false", "false", "skipped", "skipped", "skipped", false,
      "success", "false", "skipped", "skipped", "skipped", "false", required]);
  }
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
    $env:UI_REQUIRED = $case[1]
    $env:POSIX_REQUIRED = $case[13]
    $env:CONTRACTS_REQUIRED = $case[14]
    $env:DOCUMENTATION_REQUIRED = $case[2]
    $env:SKILLS_REQUIRED = $case[3]
    $env:CODE_RESULT = $case[4]
    $env:DOCUMENTATION_RESULT = $case[5]
    $env:SKILLS_RESULT = $case[6]
    $env:GITLEAKS_RESULT = $case[8]
    $env:WORKFLOWS_REQUIRED = $case[9]
    $env:WORKFLOWS_RESULT = $case[10]
    $env:UI_RESULT = $case[11]
    $env:POSIX_RESULT = $case[12]
    $passed = $true
    try { & (Join-Path $PSScriptRoot 'gate.ps1') } catch { $passed = $false }
    if ($passed -ne $case[7]) { throw "Unexpected gate outcome: $case" }
}
Write-Output "Verified $($cases.Count) workflow gate cases."
`);
    const result = spawnSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass",
      "-File", runner], { cwd: root, encoding: "utf8", timeout: 30000 });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /Verified 64 workflow gate cases/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
