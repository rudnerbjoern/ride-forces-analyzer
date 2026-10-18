# Node dependency verification

Node is development tooling, not an application runtime dependency.
Current overrides come from `package.json` and `package-lock.json`:

- smol-toml 1.9.1 replaces vulnerable 1.8.0 for the actual TOML consumers;
  [vendor advisory](https://github.com/squirrelchat/smol-toml/security/advisories/GHSA-r4xh-jqrq-34v2).
- micromark-extension-math uses KaTeX 0.19.0, crossing its declared range to fix
  inherited trust handling; compatibility is regression-tested, not universally
  assumed. [Vendor advisory](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7).

## Advisory boundary

The 2026-10-13 audit reports the braces 3.0.3 advisory
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
(CVE-2026-93687), with no patched release found on that check date. A native
bounded probe reproduced stack exhaustion at 4,500 nesting levels/9,001 characters.
The [maintainer disputes the advisory](https://github.com/micromatch/braces/issues/70);
that does not negate the observed failure. Project globs are small configured
patterns, with no application API accepting arbitrary glob input.

The recorded `npm audit --json` exits 1 with one advisory/five affected packages;
smol-toml and KaTeX are absent from those findings. This is scoped audit evidence,
not a fresh online check or a claim of a clean audit. No alert is dismissed.
Do not force dependency downgrades or remove overrides without reviewing resolved
locks and affected tests. Editor extension bundles and native Python binaries are
outside this Node audit. [Update policy](../development/DEPENDABOT.md) defines maintenance.

## Compatibility boundary

Native Windows Node 26.11.1/npm 11.20.0, tested override revision
`62b10dfd27d725ddac656bbeb645d59e530602e1`.
`npm run test:dependencies` passed its real-consumer TOML, inherited-trust and
micromark rendering checks. This verifies the tested override behavior, not all
upstream consumers, current advisories or a fresh online audit.
