---
name: release-readiness
description: Run TaskFlow's nine-point release-readiness check against a set of changed files before calling any change done. Use whenever a diff, patch, or branch is proposed as finished.
---

# Release-Readiness Check

Run these nine checks, in order, against the changed files. Report a
real pass, fail, or "could not determine" for every single one — never
a vague overall summary. A check marked "could not determine" is not the
same as a pass; say explicitly what would be needed to complete it.
Where a check genuinely does not apply to the files under review (for
example, no migration file was touched), report "not applicable" and
say why — do not silently omit it or count it as a pass.

1. **Changed files** — list every file touched, with a one-line description of what changed in each.
2. **Affected tests** — list every test file that exercises the changed code, whether or not it was itself modified.
3. **Focused test validation** — actually run just the affected tests and report the real pass/fail result, not an assumption that they'd pass.
4. **API compatibility** — for any changed endpoint, state whether its request or response shape changed. No change is a pass; an undocumented change is a fail.
5. **Migration safety** — for any new or changed migration file, confirm it has a working `downgrade()` by actually calling it in a test and inspecting the resulting schema, not by reading the code.
6. **Error handling** — for any new code path, confirm error handling exists and describe what it does on failure.
7. **Logging** — for any new or changed logging call, confirm it does not include `assignee_email`, `description`, or any other personal or free-text user data.
8. **Outbound call timeouts** — for any new or changed outbound HTTP call, confirm an explicit timeout is set.
9. **Structured report** — end with a report listing all nine checks and their result (pass / fail / not applicable / could not determine). A change is release-ready only if every check passed or was genuinely not applicable.
