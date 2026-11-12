---
name: documentation-maintenance
description: Route Ride Forces Analyzer documentation changes to their intended audience and authoritative topic, and independently review substantive user-facing changes. Use before documentation edits, including updates accompanying implementation or acceptance work.
---

# Documentation maintenance

Use [AGENTS.md](../../../AGENTS.md) and the existing
[document ownership index](../../../docs/README.md). This workflow owns the editing
and review procedure; it does not redefine document ownership or grant Git permission.

## Before writing

For substantive documentation changes, record a short scope table in
`.tmp/documentation-scope.md`: exact target file, audience, requested change or
observed behavior, and why that document owns the information. Reuse it during
the task. For spelling, whitespace or formatting-only fixes that cannot change
meaning or navigation, identify the scope in the working context without creating
a separate table.
For user-facing content, name the concrete installation decision, user action or
practical limitation that the text helps the reader handle.

An explicit request to improve a user guide is also a valid reason; no product
behavior change is necessary. General instructions to keep documentation current
are not a reason to copy information into every document.

An implementation/test/acceptance status change belongs in its authoritative
technical document. Leave user-facing files unchanged unless the task also changes
user instructions or a practical limitation, or explicitly requests their revision.
Route information by purpose, not terminology or filename alone. The README's
user-facing sections require the same audience discipline as `docs/user/`.

Edit only the justified destinations. Keep the scope/review notes temporary;
do not add them to user guides or accumulate them as tracked work reports.

## Independent review of user-facing changes

When a task materially changes user-facing instructions, claims, links or
limitations, delegate a read-only review to an independent subagent before
completion or Git delivery. Purely mechanical fixes without any change to
meaning or navigation need only a focused self-check. For substantive changes,
provide the owner's task,
scope table, ownership index, exact diff and enough surrounding document text to
identify its audience and purpose. Include both staged and unstaged task changes;
preserve owner changes. Do not supply the author's intended verdict or ask the
reviewer to justify the edit.

The reviewer must assess every added or substantially changed passage:

- Does it serve this document's audience and stated purpose?
- Is there a concrete task-related reason for putting it here?
- Does it help the user install, operate or handle a relevant limitation, rather
  than report internal implementation, verification or delivery work?
- Does it duplicate information owned by a technical document without a user need?

Request a pass/fail verdict with file/line findings and reasons. Review meaning,
not vocabulary: rewording misplaced content does not make it appropriate. Genuine
user limitations remain valid, expressed through their practical consequences.

Retain the verdict in `.tmp/`. Resolve findings and review affected passages again;
reuse the verdict while the reviewed content and task scope are unchanged. Do not
claim an independent review if it did not occur. If delegation is unavailable,
report the missing review instead of silently replacing it with self-review.

For structural changes, update incoming and outgoing references to moved or
renamed sections. Verify that each affected link leads to the intended topic or
evidence, not merely a valid path or anchor. Preserve documented stable links;
do not add compatibility aliases without an identified need. Check the actual
renderer when its heading-anchor behavior is relevant.

Before declaring completion, inspect the resulting documents against the
requested purpose and ownership, not only the checks performed. Run only affected
existing documentation checks. Formatting/link checks do not establish semantic
suitability; independent review does not replace those checks.
