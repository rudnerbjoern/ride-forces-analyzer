# Source releases

The [source-release workflow](../../.github/workflows/source-release.yml) publishes
GitHub releases for owner-authorized pushes of `v*` tags. It runs on native Windows
and publishes source only, with no installer or bundled Python, Qt or FFmpeg.
Local acceptance and owner review still precede tag creation; CI is secondary
validation. [Windows setup](SETUP.md) owns the required local checks.

## Release policy

- The tag must exactly equal `v` plus `project.version`. Supported versions are
  three numeric components, optionally followed by an `a`, `b` or `rc` number.
- The tag, event SHA and checkout must identify the same commit. The commit must
  be contained in `origin/main` and associated with a merged PR targeting this
  repository's `main`. Full CI, including mandatory Gitleaks history scanning,
  must pass for that same revision.
- All `0.x` versions and versions with `a`, `b` or `rc` suffixes are prereleases.
  Plain versions from `1.0.0` onward are stable releases.
- Source validation checks license/setup files, rejects local/binary artifacts,
  and verifies all original recording bytes against the fixture inventory.
  Wheel and source-distribution builds must also succeed.
- Only the publication job receives `contents: write`. It downloads this run's
  verified source ZIP, checksum and notes, checks the ZIP checksum, and rechecks
  the remote tag target immediately before publication.
- Publication uses `gh release create --verify-tag`, attaches the ZIP/checksum and
  combines the maintained [release text](RELEASE_NOTES.md) with generated change
  notes. Existing releases are not edited or overwritten; failed or ambiguous
  publication requires remote-state inspection before retrying.

The tag target is rechecked before publication; this is not an atomic lock against
concurrent remote tag changes. Do not move published version tags.

## Distribution boundaries

The program is GPL-3.0-or-later. The five authorized full recordings, including
GPS/metadata, and the listed documentation images have separate CC BY-SA 4.0 grants.
Original bytes and attribution notices remain intact. See
[third-party notices](../../THIRD_PARTY_NOTICES.md) before any future binary bundle.

Actions artifacts are retained for 14 days; attached GitHub release assets are
separate downloads. Existing tags do not trigger the workflow retroactively.
Hosted publication is unverified until an authorized new tag exercises this workflow.
