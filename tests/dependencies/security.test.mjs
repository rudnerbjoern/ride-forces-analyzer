import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

// cspell:words Beschleunigung échantillon
// cspell:ignore Beschleunigunng échantilllon stylessheett

// Resolve from the actual consumers, even if npm stops hoisting these packages.
const project = createRequire(import.meta.url);
const markdownCli = createRequire(project.resolve("markdownlint-cli2"));
const spellConfig = createRequire(project.resolve("cspell-config-lib"));
const markdown = createRequire(markdownCli.resolve("markdownlint"));
const mathModule = markdown.resolve("micromark-extension-math");
const mathDependencies = createRequire(mathModule);
const katex = mathDependencies("katex");
const { micromark } = await import(pathToFileURL(markdown.resolve("micromark")));
const { math, mathHtml } = await import(pathToFileURL(mathModule));

test("ESLint consumers use patched minimatch and preserve project glob matching", async () => {
  const workspace = createRequire(new URL("../../plugins/stream-deck/package.json", import.meta.url));
  const eslint = createRequire(workspace.resolve("eslint"));
  const eslintMetadata = JSON.parse(await readFile(eslint.resolve("minimatch/package.json"), "utf8"));
  assert.equal(eslintMetadata.version, "11.0.1");
  assert.equal(eslint("minimatch").minimatch("src/action.ts", "src/**/*.ts"), true);
  const typescriptEslint = createRequire(workspace.resolve("typescript-eslint"));
  const parser = createRequire(typescriptEslint.resolve("@typescript-eslint/typescript-estree"));
  const metadata = JSON.parse(await readFile(parser.resolve("minimatch/package.json"), "utf8"));
  assert.equal(metadata.version, "11.0.1");
  const { minimatch, Minimatch } = parser("minimatch");
  for (const [filename, pattern, expected] of [
    ["src/action.ts", "src/**/*.ts", true],
    ["src/nested/action.ts", "src/**/*.ts", true],
    [".config.ts", "*.ts", true],
    ["src/action.mjs", "src/**/*.ts", false],
  ]) {
    assert.equal(minimatch(filename, pattern, { dot: true }), expected, filename);
  }
  const amplified = new Minimatch("a/**/../b/**/../c/**/../d/**/../e/*.ts", {
    optimizationLevel: 2,
    braceExpandMax: 8,
  });
  assert.ok(amplified.globParts.length <= 8, "Glob preprocessing ignored its expansion limit");
  const lock = JSON.parse(await readFile(new URL("../../package-lock.json", import.meta.url), "utf8"));
  for (const [location, dependency] of Object.entries(lock.packages)) {
    if (!location.endsWith("node_modules/minimatch")) continue;
    const major = Number(dependency.version.split(".")[0]);
    assert.ok(major < 7 || major >= 11 && dependency.version !== "11.0.0",
      `Vulnerable minimatch ${dependency.version}: ${location}`);
  }
});

for (const [language, correct, typo] of [
  ["de", "Beschleunigung", "Beschleunigunng"],
  ["fr", "échantillon", "échantilllon"],
]) {
  test(`CSpell checks the ${language} catalog, rejects typos and keeps its dictionary file-scoped`, async () => {
    const filename = `src/ride_forces_analyzer/i18n/${language}.py`;
    const root = new URL("../../", import.meta.url);
    const original = await readFile(new URL(filename, root), "utf8");
    const cli = fileURLToPath(import.meta.resolve("cspell/bin.mjs"));
    for (const [path, text, expected] of [
      [filename, original, 0],
      [filename, original + `\n# ${typo}\n`, 1],
      ["src/ride_forces_analyzer/i18n/__init__.py", `# ${correct}\n`, 1],
    ]) {
      const result = spawnSync(process.execPath,
        [cli, "lint", `stdin://${path}`, "--config", ".cspell.json", "--no-progress"],
        { cwd: fileURLToPath(root), input: text, encoding: "utf8", timeout: 30000 });
      const output = result.stdout + result.stderr;
      assert.ifError(result.error);
      assert.equal(result.status, expected, output);
      if (expected === 1) {
        assert.ok(output.includes(path === filename ? typo : correct), output);
      }
    }
  });
}

test("CSpell checks skill Markdown consistently across editor language ids", () => {
  const root = fileURLToPath(new URL("../../", import.meta.url));
  const cli = fileURLToPath(import.meta.resolve("cspell/bin.mjs"));
  const skill = ".agents/skills/update-screenshots/SKILL.md";
  for (const [filename, languageId, word, expected] of [
    [skill, "markdown", "stylesheet", 0],
    [skill, "instructions", "stylesheet", 0],
    [skill, "instructions", "stylessheett", 1],
    ["README.md", "instructions", "stylesheet", 1],
  ]) {
    const result = spawnSync(process.execPath,
      [cli, "lint", `stdin://${filename}`, "--config", ".cspell.json", "--no-progress",
        "--language-id", languageId],
      { cwd: root, input: `${word}\n`, encoding: "utf8", timeout: 30000 });
    const output = result.stdout + result.stderr;
    assert.ifError(result.error);
    assert.equal(result.status, expected, output);
    if (expected === 1) assert.ok(output.includes(word), output);
  }
});

test("Documentation and lint consumers share the declared Markdown parser release", async () => {
  const manifest = JSON.parse(await readFile(new URL("../../package.json", import.meta.url), "utf8"));
  const expected = manifest.devDependencies["markdown-it"];
  assert.equal(manifest.overrides["markdownlint-cli2"]["markdown-it"], expected);
  for (const consumer of [project, markdownCli, markdown]) {
    const metadata = JSON.parse(await readFile(consumer.resolve("markdown-it/package.json"), "utf8"));
    assert.equal(metadata.version, expected, consumer.resolve("markdown-it"));
    const { default: MarkdownIt } = await import(pathToFileURL(consumer.resolve("markdown-it")));
    const html = new MarkdownIt("commonmark").render("[ride][ref]\n\n[ref]: https://example.com\n");
    assert.equal(html, '<p><a href="https://example.com">ride</a></p>\n');
  }
});

test("Markdownlint uses patched RE2JS and still detects spaces inside links", async () => {
  const metadata = JSON.parse(await readFile(
    new URL("../package.json", pathToFileURL(markdown.resolve("re2js"))), "utf8"));
  assert.equal(metadata.version, "2.8.7");
  const { lint } = await import(pathToFileURL(markdownCli.resolve("markdownlint/promise")));
  const result = await lint({
    strings: { sample: "[ ride](https://example.com)\n" },
    config: { default: false, MD039: true },
  });
  assert.deepEqual(result.sample.map(error => error.ruleNames[0]), ["MD039"]);
});

for (const [name, consumer] of [["markdownlint", markdownCli], ["CSpell", spellConfig]]) {
  test(`${name} TOML parser preserves flat keys and nested configuration`, () => {
    const { parse } = consumer("smol-toml");
    const flat = Array.from({ length: 2048 }, (_, index) => `key${index} = ${index}`);
    const source = [...flat, '[window]', 'title = "Ride Forces Analyzer"',
      'dimensions.width = 900', 'dimensions.height = 600'].join("\n");
    const result = parse(source);
    for (let index = 0; index < flat.length; index += 1) {
      assert.equal(result[`key${index}`], index);
    }
    // New parser releases return tables without Object.prototype; compare data.
    assert.equal(result.window.title, "Ride Forces Analyzer");
    assert.equal(result.window.dimensions.width, 900);
    assert.equal(result.window.dimensions.height, 600);
    assert.deepEqual(Object.keys(result.window).sort(), ["dimensions", "title"]);
  });
}

test("KaTeX rejects inherited trust for a JavaScript link", () => {
  const options = Object.create({ trust: true });
  const html = katex.renderToString(String.raw`\href{javascript:alert(1)}{link}`, options);
  assert.ok(!html.includes('href="javascript:'), "Inherited trust allowed an unsafe link");
});

for (const expression of [String.raw`x^2 + y^2`, String.raw`\frac{1}{2}`,
  String.raw`\sum_{i=1}^{n} i`]) {
  test(`micromark math renderer accepts ${expression}`, () => {
    const html = micromark(`Math $${expression}$\n`, {
      extensions: [math()],
      htmlExtensions: [mathHtml({ throwOnError: true })],
    });
    assert.match(html, /math-inline/);
    assert.match(html, /class="katex"/);
  });
}
