import { spawnSync } from "node:child_process";
import { appendFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const codeInputs = new Set([
  "pyproject.toml", "uv.lock", ".python-version", ".node-version",
  "package.json", "package-lock.json", ".gitignore", ".gitattributes", ".editorconfig",
  ".vscode/settings.json",
  ".github/dependabot.yml",
]);

export function classifyChanges(filenames) {
  let code = false;
  let documentation = false;
  for (const filename of filenames) {
    if (filename.toLowerCase().endsWith(".md")) {
      documentation = true;
      continue;
    }
    if (filename.startsWith("src/") || filename.startsWith("tests/")
      || filename.startsWith(".github/workflows/")
      || filename.startsWith(".github/scripts/") || codeInputs.has(filename)
      || /\.(?:py|pyi|js|mjs|cjs|ps1|sh|bat|cmd)$/.test(filename)) {
      code = true;
    }
  }
  return { code, documentation };
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
    `code=${selection.code}\ndocumentation=${selection.documentation}\n`, "utf8");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const selection = classifyChanges(changedPaths(process.env.PR_BASE_SHA, process.env.PR_HEAD_SHA));
  writeOutputs(selection, process.env.GITHUB_OUTPUT);
  console.log(`Code checks: ${selection.code}; documentation checks: ${selection.documentation}`);
}
