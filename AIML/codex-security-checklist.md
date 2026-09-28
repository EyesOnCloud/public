# TaskFlow Security and Reliability Checklist

Apply these checks to changed application files.

## SQL safety

Inspect sqlite3 calls.

Prefer parameterized SQL such as:

conn.execute(
    "SELECT * FROM tasks WHERE id = ?",
    (task_id,),
)

Flag SQL built using untrusted values through:

- f-strings
- %-formatting
- string concatenation

## Dynamic code execution

Look for:

eval(

exec(

These require explicit justification.

## Secrets

Look for newly hard-coded:

- passwords
- API keys
- tokens
- authorization headers
- credentials

## External URLs

Review hard-coded external service URLs.

A known test fixture is not automatically a production security issue,
but production endpoints should be intentional.

## HTTP reliability

Follow AGENTS.md.

Outbound HTTP requests must use an explicit timeout.

## Bulk outbound behavior

Follow AGENTS.md.

Any request capable of triggering multiple outbound calls must be
bounded, capped, rate-limited, or otherwise controlled.

## Logging

Never expose:

- assignee_email
- description
- values derived from either field

## Result

Record concrete evidence.

Do not report PASS only because no obvious problem was noticed.
