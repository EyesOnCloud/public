# TaskFlow API Compatibility Checklist

Use this checklist only when app/main.py changes.

## Routes

Verify that existing public routes have not accidentally been removed,
renamed, or changed.

TaskFlow currently exposes operations for:

- creating tasks;
- retrieving an individual task;
- listing tasks;
- updating task status/priority;
- bulk notification.

## Check

Review:

1. HTTP method
2. route path
3. required request fields
4. optional request fields
5. response status codes
6. response JSON structure
7. previously valid requests

Compare the current version with the merge base.

Useful commands:

git diff start...HEAD -- app/main.py

git show start:app/main.py

Do not automatically classify every API change as a failure.

A documented intentional change may be WAIVED with a clear reason.

An accidental breaking change is FAIL.
