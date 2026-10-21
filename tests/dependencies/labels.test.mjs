import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

// Reuse the locked YAML parser already consumed by CSpell.
const project = createRequire(import.meta.url);
const configConsumer = createRequire(project.resolve("cspell-config-lib"));
const { parseDocument } = configConsumer("yaml");
// CSpell's locked glob consumer supports dot files, as the labeler does by default.
const globConsumer = createRequire(import.meta.resolve("cspell-glob"));
const picomatch = globConsumer("picomatch");

function parse(source) {
  const document = parseDocument(source, { uniqueKeys: true });
  assert.deepEqual(document.errors, [], "Label YAML must have no errors or duplicate keys");
  return document.toJS();
}

const rules = parse(await readFile(new URL("../../.github/labeler.yml", import.meta.url), "utf8"));
const workflow = parse(await readFile(new URL("../../.github/workflows/labeler.yml", import.meta.url), "utf8"));

test("Issue templates assign their intended type without requiring additional labels", async () => {
  for (const [filename, label] of [["bug_report", "bug"], ["feature_request", "enhancement"]]) {
    const source = await readFile(new URL(`../../.github/ISSUE_TEMPLATE/${filename}.md`, import.meta.url), "utf8");
    const header = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
    assert.ok(header, "Issue template requires YAML front matter");
    const metadata = parse(header[1]);
    assert.ok(metadata.name.length > 3 && metadata.about);
    assert.equal(metadata.labels, label);
  }
});

test("PR labels cover nested Markdown, dependency locks and CI without labeling ordinary source", () => {
  // Test the intentionally simple path-glob policy locally, not the hosted action/API.
  function labelsFor(filenames) {
    return Object.entries(rules).filter(([, configs]) => configs.some(config =>
      config["changed-files"].some(rule => {
        const globs = [rule["any-glob-to-any-file"]].flat();
        return filenames.some(filename => globs.some(glob => picomatch.isMatch(filename, glob, { dot: true })));
      }))).map(([label]) => label).sort();
  }
  const cases = [
    [["README.md"], ["documentation"]],
    [["docs/architecture/08_concepts.md"], ["documentation"]],
    [[".github/ISSUE_TEMPLATE/bug_report.md"], ["documentation"]],
    [["uv.lock", "package-lock.json"], ["dependencies"]],
    [[".github/dependabot.yml"], ["dependencies"]],
    [[".github/workflows/ci.yml"], ["ci"]],
    [[".github/labeler.yml", "tests/ci/changes.test.mjs"], ["ci"]],
    [[".github/release.yml"], ["ci"]],
    [["README.md", "pyproject.toml", ".github/scripts/ci-changes.mjs"],
      ["ci", "dependencies", "documentation"]],
    [["src/ride_forces_analyzer/importers/service.py", "tests/test_service.py"], []],
    [["tests/fixtures/real/example.forces", "docs/chart.svg"], []],
    [[], []],
  ];
  assert.deepEqual(Object.keys(rules).sort(), ["ci", "dependencies", "documentation"]);
  for (const [files, expected] of cases) {
    assert.deepEqual(labelsFor(files), expected, JSON.stringify(files));
  }
});

test("Release notes categorize typed and automatic PR labels and retain unlabelled changes", async () => {
  const release = parse(await readFile(new URL("../../.github/release.yml", import.meta.url), "utf8"));
  const categories = release.changelog.categories;
  assert.deepEqual(release.changelog.exclude ?? {}, {});
  assert.deepEqual(categories.at(-1).labels, ["*"]);
  const knownLabels = new Set(["bug", "enhancement", ...Object.keys(rules), "*"]);
  for (const category of categories) {
    assert.ok(category.title.trim());
    assert.deepEqual(category.exclude ?? {}, {});
    for (const label of category.labels) {
      assert.ok(knownLabels.has(label), `Unknown release category label: ${label}`);
    }
  }
  for (const [labels, title] of [
    [["bug", "documentation"], "Fixes"],
    [["enhancement", "documentation"], "Improvements"],
    [["dependencies", "ci"], "Dependencies"],
    [["documentation"], "Documentation"],
    [["ci"], "Maintenance"],
    [["unclassified"], "Other changes"],
    [[], "Other changes"],
  ]) {
    const category = categories.find(item => item.labels.some(label => label === "*" || labels.includes(label)));
    assert.equal(category?.title, title, JSON.stringify(labels));
  }
});

test("Label automation runs only for PR metadata with minimal permissions and no PR execution", () => {
  assert.deepEqual(workflow.on, {
    pull_request_target: { branches: ["main"], types: ["opened", "synchronize", "reopened"] },
  });
  assert.deepEqual(workflow.permissions, { contents: "read", "pull-requests": "write" });
  assert.deepEqual(Object.keys(workflow.jobs), ["label"]);
  const job = workflow.jobs.label;
  assert.equal(job["runs-on"], "windows-latest");
  assert.ok(job["timeout-minutes"] > 0 && job["timeout-minutes"] <= 5);
  assert.equal(job.steps.length, 1, "No checkout, scripts or PR code execution");
  const step = job.steps[0];
  assert.match(step.uses, /^actions\/labeler@v\d+\.\d+\.\d+$/);
  assert.deepEqual(step.with, { "sync-labels": false }, "Preserve manual labels");
  assert.ok(!Object.hasOwn(step, "run"));
});
