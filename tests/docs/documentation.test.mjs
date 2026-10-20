import assert from "node:assert/strict";
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import MarkdownIt from "markdown-it";

const root = fileURLToPath(new URL("../../", import.meta.url));
const markdown = new MarkdownIt("commonmark");

async function markdownFiles(directory, recursive) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isFile() && entry.name.endsWith(".md")) {
      files.push(filename);
    } else if (recursive && entry.isDirectory()) {
      files.push(...await markdownFiles(filename, true));
    }
  }
  return files.sort();
}

const documents = [
  ...await markdownFiles(root, false),
  ...await markdownFiles(path.join(root, "docs"), true),
  ...await markdownFiles(path.join(root, ".github"), true),
  ...await markdownFiles(path.join(root, ".agents/skills"), true),
];

assert.ok(documents.length > 0, "No documentation files found");

test("Website navigation reaches sections in the shared README", async () => {
  const readme = await readFile(path.join(root, "README.md"), "utf8");
  const layout = await readFile(path.join(root, "_layouts/default.html"), "utf8");
  const tokens = markdown.parse(readme, {});
  const headings = new Set();
  for (let index = 0; index < tokens.length; index += 1) {
    if (tokens[index].type === "heading_open" && tokens[index].tag === "h2") {
      headings.add(tokens[index + 1].content.toLowerCase().replace(/[^a-z0-9 -]/g, "").replaceAll(" ", "-"));
    }
  }
  const navigation = layout.match(/<nav\b[^>]*>[\s\S]*?<\/nav>/)?.[0];
  assert.ok(navigation, "Missing main navigation");
  const targets = [...navigation.matchAll(/href="#([^"]+)"/g)].map(match => match[1]);
  assert.ok(targets.length > 0, "No section links in navigation");
  for (const target of targets) {
    assert.ok(headings.has(target), `Navigation target missing from README: ${target}`);
  }
});

for (const filename of documents) {
  test(`local links in ${path.relative(root, filename)}`, async () => {
    const source = await readFile(filename, "utf8");
    for (const block of markdown.parse(source, {})) {
      for (const token of block.children ?? []) {
        const href = token.type === "link_open" ? token.attrGet("href")
          : token.type === "image" ? token.attrGet("src") : null;
        if (!href || href.startsWith("//") || /^[a-z][a-z\d+.-]*:/i.test(href)) {
          continue;
        }
        // External URLs and fragments are deliberately not fetched or validated.
        const localPath = decodeURIComponent(href.split(/[?#]/, 1)[0]);
        if (!localPath) {
          continue;
        }
        const target = localPath.startsWith("/")
          ? path.resolve(root, localPath.slice(1))
          : path.resolve(path.dirname(filename), localPath);
        const relative = path.relative(root, target);
        assert.ok(!relative.startsWith(`..${path.sep}`) && relative !== ".."
          && !path.isAbsolute(relative), `Link leaves the repository: ${href}`);
        let exists;
        try {
          const info = await stat(target);
          exists = info.isFile() || info.isDirectory();
        } catch (error) {
          if (error.code !== "ENOENT") {
            throw error;
          }
          exists = false;
        }
        assert.ok(exists, `Missing local link target: ${href}`);
      }
    }
  });
}
