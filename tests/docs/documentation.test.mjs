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
];

assert.ok(documents.length > 0, "No documentation files found");

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
