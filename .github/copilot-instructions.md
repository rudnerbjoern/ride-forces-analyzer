# Repository instructions

Follow the repository-wide engineering and validation rules in `AGENTS.md`.

Never commit on `main` or push to remote `main`. Create a dedicated working branch
from `main` and transfer changes exclusively through a pull request targeting
`main`. Verify the active branch before an authorized commit and the explicit
destination ref before an authorized push. These instructions do not grant
permission to stage, commit, push or merge.

When generating or proposing a Git commit message, read and follow
`.github/commit-message-instructions.md`. Base the message exclusively on the
staged changes and do not infer test results, issue identifiers, or rationale.
