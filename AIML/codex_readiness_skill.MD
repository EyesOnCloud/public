---
name: production-readiness
description: >
  Run TaskFlow's production-readiness validation before claiming a code
  change is ready to merge, ship, release, or deploy. Use when reviewing
  release readiness, when explicitly asked for a production-readiness
  check, or after changes to app/ or migrations/ that are being prepared
  for completion. Do not use for simple explanations or unrelated
  code-reading requests.
---

# TaskFlow Production Readiness

Use this workflow when determining whether a TaskFlow change is ready
to merge, ship, release, or deploy.

Follow the steps in order.

Do not mark a check PASS without evidence from repository files or a
command that was actually executed.

## 1. Identify changed services

Run:

python .agents/skills/production-readiness/scripts/changed_services.py

Record the changed application files.

If no application or migration files changed, record that result
explicitly.

## 2. Find affected tests

Run:

python .agents/skills/production-readiness/scripts/affected_tests.py <changed-files>

Use the files identified in step 1.

Record every affected test file.

If application code changed and no relevant test is found, mark this
check FAIL.

## 3. Run focused validation

Run pytest against exactly the affected tests identified in step 2.

Example:

pytest -q tests/test_notify.py

Record the pytest summary.

A changed application module with no runnable affected tests is a FAIL,
not a skipped check.

## 4. Check API compatibility

If app/main.py changed, read:

references/api-compatibility.md

Compare the changed routes and externally visible request/response
behavior against the baseline.

If app/main.py did not change:

WAIVED — app/main.py unchanged.

## 5. Review database changes

If migrations/ changed:

- inspect every changed migration;
- verify upgrade() exists;
- verify downgrade() exists;
- verify downgrade() performs a real reversal;
- run migration tests when available.

Follow AGENTS.md.

If migrations/ did not change:

WAIVED — no migration changes.

## 6. Check error handling

Inspect every changed Python file.

Check for:

- bare except:
- broadly swallowed exceptions;
- except Exception blocks that neither log nor re-raise;
- retry loops that hide permanent failures;
- error paths that silently return success.

Record the evidence.

## 7. Verify logs and observability

Inspect logger calls in changed files.

Follow AGENTS.md.

Specifically verify that:

- assignee_email is not logged;
- description is not logged;
- values derived from those fields are not logged.

Mark FAIL if changed code introduces prohibited logging.

## 8. Review security and reliability risks

Read:

references/security-checklist.md

Apply the checklist to all changed files.

Record findings and commands used.

## 9. Generate the release report

Read:

assets/report-template.md

Write the final report to:

RELEASE_REPORT.md

Do not create a READY verdict unless all required checks are PASS or
have an explicit acceptable WAIVED reason.

Do not edit the report simply to satisfy the Stop hook.

Fix the underlying problem first.

## Required terminal artifact

The workflow is not complete until RELEASE_REPORT.md exists and contains:

- checks 22 through 29;
- one status for every check;
- evidence for every status;
- a final VERDICT line.

Allowed statuses:

PASS
FAIL
WAIVED

Allowed verdicts:

READY
NOT READY
