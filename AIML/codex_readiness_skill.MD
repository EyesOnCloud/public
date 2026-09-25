---
name: production-readiness
description: >
  Run the nine-point production-readiness checklist against a changed
  TaskFlow service before claiming a change is ready to ship. Use when
  asked "is this ready to merge/ship/release", before ending a session
  that modified app/ or migrations/, or when explicitly invoked as
  /production-readiness. Do not use for unrelated code review requests
  that aren't about release readiness.
---

# Production Readiness Check

Run these nine steps **in order**. Do not skip a step because it looks
irrelevant to this change — record it as PASS with a one-line reason
instead. Do not mark anything PASS without evidence (a command you ran,
a file you read) cited next to it.

1. **Identify changed services.** Run `scripts/changed_services.sh`.
   Record the output verbatim.
2. **Find affected tests.** Run `scripts/affected_tests.sh` against the
   changed files from step 1.
3. **Run focused validation.** Run `pytest -q` scoped to exactly the
   test files step 2 found. Record the pass/fail counts. Zero tests
   collected is a FAIL for this step, not a skip.
4. **Check API compatibility.** If `app/main.py` changed, read
   `reference/api-compatibility.md` and diff the route table against
   the previous commit.
5. **Review database changes.** If anything under `migrations/`
   changed, confirm the new/modified file defines both `upgrade()` and
   a `downgrade()` that is not a no-op.
6. **Check error handling.** Grep every changed file for bare
   `except:` and `except Exception` blocks that don't log or re-raise.
7. **Verify logs and metrics.** Grep every changed file's `logger.*`
   calls for `assignee_email` or `description` per AGENTS.md's logging
   rule.
8. **Review security risks.** Read `reference/security-checklist.md`
   and apply it to every changed file.
9. **Generate the structured release report.** Use
   `reference/report-template.md`. Write it to `RELEASE_REPORT.md` at
   the repo root. Every one of steps 1–8 gets exactly one line: `PASS`,
   `FAIL`, or `WAIVED: <reason>`. The final line is `VERDICT: READY` or
   `VERDICT: NOT READY` — READY requires zero unwaived FAILs.

A Stop hook reads `RELEASE_REPORT.md` before this session is allowed to
end. An incomplete, missing, or malformed report — or an unwaived FAIL
under a READY verdict — will block completion and hand the reason back
to you. Fix the real problem the report identifies; do not edit the
report to make the hook pass.
