# Documentation tests

Install the locked Node tools through [Windows setup](SETUP.md), then run:

```powershell
npm run test:docs
```

The suite works offline and combines `lint:docs`, `spellcheck` and
`test:docs:links`; each can also run separately. It does not modify files or fetch
external targets. [CI selection](CI.md) defines when the documentation job runs.

## Scope and limitations

| Check        | Configuration / behavior                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Markdownlint | `.markdownlint-cli2.jsonc`: root Markdown, `docs/`, `.github/` and `.agents/skills/`; default rules except MD013/MD036, aligned MD060 tables; respects Git ignores |
| CSpell       | `.cspell.json`: English, case-insensitive language settings and bundled Python dictionary; shared with VS Code; checks configured code/docs/configuration patterns |
| Local links  | `tests/docs/documentation.test.mjs`: markdown-it parses links/images in root/docs/GitHub/skill Markdown; targets must exist inside the repository                  |

CSpell excludes environments, dependencies, temporary/build outputs, lock files
and `.forces`. Correct spelling errors; add only legitimate project/tool names.
Link tests resolve relative paths from each document and leading slashes from the
repository root. They skip links inside code, external URLs, query strings and
heading fragments; they verify neither external availability nor anchor spelling.
Fixture links check existence without parsing or modifying recordings.

Recommended VS Code extensions consume the same Markdown/CSpell configuration.
CLI success does not establish interactive editor feedback or Mermaid rendering.
Changed Mermaid definitions require a separate syntax check; report visual limits.
