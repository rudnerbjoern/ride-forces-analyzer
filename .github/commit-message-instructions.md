# Ride Forces Analyzer commit messages

Follow [AGENTS.md](../AGENTS.md) for authorization, staged-file protection and
required validation. This guide defines message content; it does not authorize
staging or committing. Generate a message only for the approved staged changes.
If nothing is staged, do not infer a commit message from the working tree.

Commits belong on a dedicated working branch created from `main`. Never commit on
`main` or push to remote `main`; changes reach `main` exclusively through a pull
request targeting it. Verify the branch before any authorized commit and the
explicit destination ref before any authorized push, as required by AGENTS.md.

Use English and this header:

```text
:<icon>: <type>(<scope>): <imperative outcome>
```

Requirements:

- Keep the raw header, including the shortcode, at or below 80 characters.
- Use lower-case `type` and `scope`; require one concise capability scope.
- Start the summary with a lower-case imperative verb and omit its final period.
- Describe the outcome, not a file list.
- Use exactly one deterministic type and icon:
  - `:sparkles: feat`
  - `:bug: fix`
  - `:recycle: refactor`
  - `:zap: perf`
  - `:test_tube: test`
  - `:memo: docs`
  - `:package: build`
  - `:gear: ci`
  - `:wrench: chore`
- Prefer a Ride Forces Analyzer capability scope: `recordings` for source-file
  integrity and fixtures, `imports` for recording ingestion, `analysis` for
  calibration and G-force calculations, `storage` for the local ride library,
  `playback` for the timeline, `rendering` for frames and exports, `sync` for POV
  video synchronization, `gui` for desktop interactions, or `config` for
  application settings. Use a scope only when the staged change affects it;
  most product capabilities remain planned beyond M1.
- Use `foundation`, `docs`, `tests`, `deps`, `ci`, `tooling`, or `packaging` for
  project scaffolding or genuinely cross-cutting development changes.
- Choose the type from the primary outcome: `feat` adds behavior, `fix` corrects
  behavior, `refactor` preserves behavior, `perf` improves performance, `test`
  changes test coverage, `docs` changes documentation, `build` changes packaging
  or dependency resolution, `ci` changes workflows, and `chore` covers other
  maintenance. The icon must match that type exactly.
- Omit the body for a small self-explanatory change.
- Otherwise add `Why:` followed by the motivation, then `Changes:` with only
  the material effects.
- Add `Refs: #<number>` for an actual GitHub issue reference or
  `Fixes: #<number>` only when the change resolves that issue. Use a full issue
  URL for cross-repository references. Do not carry over identifiers from other
  projects.
- Add `Refs: M1` (or the applicable milestone from
  [the roadmap](../docs/ROADMAP.md)) only when the staged change relates to that
  milestone. A milestone reference does not mean its acceptance criteria passed.
- Add a `BREAKING CHANGE:` footer for an incompatible contract or migration.
- Never invent verification results, issue identifiers, effects, or rationale.
- If describing validation, state only checks actually run on the relevant
  revision. Distinguish local Windows checks, static workflow validation and
  GitHub-hosted CI. Do not claim M1 completion while acceptance criteria are open.
- Never include secrets, personal data, or sensitive diagnostic details.
- In particular, do not include GPS positions or recording contents in messages.
  Changes involving `.forces` fixtures must preserve their original bytes.

## Header examples

These illustrate the format, not verified changes or milestone completion:

```text
:sparkles: feat(config): validate bootstrap window settings
:test_tube: test(recordings): verify authorized recording bytes
:gear: ci(ci): run Windows checks only for pull requests
:memo: docs(foundation): document open M1 acceptance criteria
```
