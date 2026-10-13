# Documentation tests

The documentation suite checks Markdown formatting, spelling and local link targets. It
runs separately from the Python application tests and requires no network after
its development dependencies have been installed.

## Setup and execution

Complete the [Windows development setup](SETUP.md) first.
Use the Node.js version recorded in `.node-version` (26.11.1) and its bundled npm.
From the repository root, run:

```powershell
$env:NPM_CONFIG_CACHE = "$PWD/.tmp/npm-cache"
npm ci --no-audit --no-fund
npm run test:docs
```

`package-lock.json` records exact dependency versions and integrity hashes.
These Node dependencies are development tools; the desktop application does
not depend on Node.js.

Individual checks can also be run:

```powershell
npm run lint:docs
npm run spellcheck
npm run test:docs:links
```

## Markdown formatting

`markdownlint-cli2` checks Markdown files at the repository root and under
`docs/` and `.github/`. `.markdownlint-cli2.jsonc` defines that scope and respects Git ignore
rules, excluding environments, dependencies, caches and temporary files.

The `config` object in `.markdownlint-cli2.jsonc` enables the default rules,
disables `MD013` (line length) and `MD036` (emphasis instead of a heading), and
sets `MD060` to require aligned table columns and delimiters. Checks report
errors without rewriting files. Markdown hard line breaks remain allowed.

The recommended VS Code markdownlint extension reads the same rule file, so
editor feedback and the suite use matching rules.

## Spelling

CSpell uses `.cspell.json` for the CLI and the recommended VS Code Code Spell
Checker extension. Workspace settings explicitly enable the extension. The
project uses English dictionaries because source code and technical documentation
are written in English. `languageSettings` disables case-sensitive checking for
Python, JavaScript, JSON/JSONC, TOML, YAML and Markdown. The bundled Python
dictionary also recognizes Python names in configuration and embedded examples.

`npm run spellcheck` checks Markdown, Python, JavaScript and configuration files.
The shared `files` patterns determine the scope, and Git ignore rules are honored.
Temporary files, environments, dependencies, build outputs, lock files and `.forces`
recordings are excluded. `words` contains approved project and tool names; real
spelling mistakes should be corrected instead of added to that list.

CSpell is a pinned development dependency in `package-lock.json`. Its bundled
local dictionaries make spell checking work offline after installation. It does
not modify checked files or fetch external link targets.

## Local link checks

The Node.js test runner executes `tests/docs/documentation.test.mjs`. Each
Markdown document at the root or under `docs/` or `.github/` has a test
that uses `markdown-it` to parse inline and
reference links and image paths. Relative targets resolve from the document's
directory; leading-slash targets resolve from the repository root. Targets must
exist and stay within the repository. Links inside code examples are ignored.

External URLs are skipped; this suite does not fetch web pages or check remote
availability. Heading fragments and query strings are excluded from target
resolution and are not validated. The [recording catalog](RECORDINGS.md) links
all four original fixtures; link tests check their existence but do not read their
contents. `.forces` recordings are never modified.

## Continuous integration

The PR-only workflow has a separate `documentation` job on `windows-latest`.
It selects Node.js from `.node-version`, installs dependencies with `npm ci`
and runs `npm run test:docs`. A lint, spelling or local-link failure fails the job.

A workflow revision requires a successful pull-request run before it can be
reported as verified on GitHub. The M1 jobs passed; see
[M1 validation](../validation/M1.md) for the inspected run and revision.
