# Codex project settings

`.codex/config.toml` contains project defaults. Workflow and safety instructions
remain in [AGENTS.md](../../AGENTS.md). Keep personal credentials out of this file.
Project defaults do not modify the user-global configuration.

## Current settings

- Model: `gpt-6.1-sol`; reasoning effort: `high`; personality: `pragmatic`.
- Web search: `cached`.
- Context7 MCP server: `npx -y @upstash/context7-mcp`.
- Memory feature enabled; `generate_memories` and `use_memories` enabled.
- `disable_on_external_context = true` excludes threads containing external context,
  such as MCP or web-search results, from memory generation.

Context7 requires Node.js/npm in the environment hosting Codex and network access
for documentation lookup. It is a development aid, not an application runtime
requirement. The server package is not pinned in this requested configuration;
it is separate from the locked Python and Node project dependencies.

Codex reads project configuration only for trusted repositories. User/profile and
CLI settings also participate in configuration precedence; project defaults do
not guarantee the active model or tool availability in every session. See the
[official configuration guide](https://learn.chatgpt.com/docs/config-file/config-basic).

The requested memory keys are documented in the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
They configure Codex behavior; they do not authorize editing memory files manually.

## Validation boundary

The file was parsed as TOML, and the local Codex CLI accepted it when listing
features with `memories` enabled. A new Codex session using all requested settings,
Context7 startup from this file and actual memory generation were not exercised.
No such runtime verification is claimed.
