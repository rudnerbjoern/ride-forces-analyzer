# Codex project settings

`.codex/config.toml` owns repository defaults; [AGENTS.md](../../AGENTS.md) owns
workflow rules. Project settings require repository trust and participate in
user/profile/CLI precedence; they do not guarantee the active session settings.
Never store credentials or operation authorization in configuration.

Current defaults: `gpt-6.1-sol`, high reasoning, pragmatic personality, cached web
search and enabled memories. `disable_on_external_context` excludes externally
sourced threads from memory generation; settings do not authorize manual memory edits.
Context7 runs through unpinned `npx -y @upstash/context7-mcp`, requiring Node/npm
and network in the Codex host. It is separate from locked application dependencies.

The file parsed as TOML and the local CLI accepted memory feature settings.
Fresh-session model/settings application, configured Context7 startup and actual
memory generation remain unverified. See the
[configuration guide](https://learn.chatgpt.com/docs/config-file/config-basic) and
[reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## Delivery tooling

The [github-delivery skill](../../.agents/skills/github-delivery/SKILL.md) is the
single source for helper commands, exact staging, commit policy, push/PR/merge
guards and its separate regression suite. Its authorization flag cannot replace
owner approval. Application pytest/Test Explorer excludes these skill tests;
[CI routing](CI.md) selects their own job only for relevant inputs.

The [CI guide](CI.md) describes check routing and verification boundaries.
Simulated helper tests do not establish fresh-session skill discovery or live GitHub behavior.
