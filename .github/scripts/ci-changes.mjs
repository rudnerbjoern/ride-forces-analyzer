import { spawnSync } from "node:child_process";
import { appendFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const codeInputs = new Set([
  "pyproject.toml", "uv.lock", ".python-version", ".node-version", "ffmpeg.json",
  "package.json", "package-lock.json", ".gitignore", ".gitattributes", ".editorconfig",
  ".vscode/settings.json",
]);

const ciInputs = new Set([
  ".github/dependabot.yml", ".github/labeler.yml", ".github/release.yml",
]);

const nativeInputs = new Set([
  ".github/workflows/ci.yml", ".github/workflows/posix-packages.yml",
]);

const skillInputs = new Set([
  "pyproject.toml", "uv.lock", ".python-version", ".gitignore", ".gitattributes", ".editorconfig",
  ".github/commit-message-instructions.md",
]);

export function classifyChanges(filenames) {
  let code = false;
  let documentation = false;
  let skills = false;
  let workflows = false;
  let dependencies = false;
  let posix = false;
  for (const filename of filenames) {
    if (filename === ".cspell.json") {
      dependencies = true;
    }
    const ci = ciInputs.has(filename)
      || filename.startsWith(".github/workflows/") || filename.startsWith(".github/scripts/")
      || filename.startsWith("tests/ci/") || filename.startsWith("tests/dependencies/");
    if (ci) {
      workflows = true;
      dependencies = true;
    }
    if (nativeInputs.has(filename)) {
      posix = true;
    }
    if (skillInputs.has(filename)) {
      skills = true;
    }
    if (filename.toLowerCase().endsWith(".md")) {
      documentation = true;
      continue;
    }
    if (filename.startsWith(".agents/skills/")) {
      skills = true;
      continue;
    }
    // Keep Python release-helper changes under the application quality checks.
    // Other CI inputs have their own syntax and Node/PowerShell contract checks.
    if (ci && !filename.endsWith(".py")) {
      continue;
    }
    if (filename.startsWith("src/") || filename.startsWith("tests/")
      || codeInputs.has(filename)
      || /\.(?:py|pyi|js|mjs|cjs|ps1|sh|bat|cmd)$/.test(filename)) {
      code = true;
    }
  }
  return { code, documentation, skills, workflows, dependencies: dependencies || code, posix: posix || code };
}

export function changedPaths(base, head, cwd = process.cwd()) {
  for (const revision of [base, head]) {
    if (typeof revision !== "string" || !/^[a-f\d]{40}$/i.test(revision)) {
      throw new Error("Expected a full commit SHA for both PR revisions");
    }
  }
  // Match the complete PR diff; include both sides of renames and deleted paths.
  const result = spawnSync("git", ["diff", "--no-renames", "--name-only", "-z",
    `${base}...${head}`, "--"], {
    cwd,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    timeout: 30000,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`Cannot determine PR changes: ${result.stderr.trim()}`);
  }
  return result.stdout.split("\0").filter(Boolean);
}

export function writeOutputs(selection, output) {
  if (!output) {
    throw new Error("GITHUB_OUTPUT is required");
  }
  appendFileSync(output,
    `code=${selection.code}\ndocumentation=${selection.documentation}\nskills=${selection.skills}\nworkflows=${selection.workflows}\ndependencies=${selection.dependencies}\nposix=${selection.posix}\n`, "utf8");
}

export function selectChecks(eventName, base, head, cwd = process.cwd(), fullChecks = false) {
  if (eventName === "workflow_dispatch" || fullChecks) {
    return { code: true, documentation: true, skills: true, workflows: true, dependencies: true, posix: true };
  }
  if (eventName === "pull_request") {
    return classifyChanges(changedPaths(base, head, cwd));
  }
  throw new Error(`Unsupported CI event: ${eventName}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const selection = selectChecks(process.env.GITHUB_EVENT_NAME, process.env.PR_BASE_SHA,
    process.env.PR_HEAD_SHA, process.cwd(), process.env.CI_FULL_CHECKS === "true");
  writeOutputs(selection, process.env.GITHUB_OUTPUT);
  console.log(`Code checks: ${selection.code}; documentation checks: ${selection.documentation}; skill checks: ${selection.skills}; workflow checks: ${selection.workflows}; dependency checks: ${selection.dependencies}; POSIX checks: ${selection.posix}`);
}
