#!/usr/bin/env python3

import subprocess
import sys


def git(*args):
    result = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


base = sys.argv[1] if len(sys.argv) > 1 else "start"

changed = set()

# 1. Changes committed after the baseline branch
try:
    merge_base = git("merge-base", base, "HEAD")

    output = git(
        "diff",
        "--name-only",
        merge_base,
        "HEAD",
        "--",
        "app/",
        "migrations/",
    )

    changed.update(
        line for line in output.splitlines()
        if line.strip()
    )

except subprocess.CalledProcessError as exc:
    print(
        f"Unable to compare against baseline {base}: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)


# 2. Staged changes
output = git(
    "diff",
    "--cached",
    "--name-only",
    "--",
    "app/",
    "migrations/",
)

changed.update(
    line for line in output.splitlines()
    if line.strip()
)


# 3. Uncommitted working-tree changes
output = git(
    "diff",
    "--name-only",
    "--",
    "app/",
    "migrations/",
)

changed.update(
    line for line in output.splitlines()
    if line.strip()
)


if not changed:
    print("NO_CHANGED_APPLICATION_FILES")
    sys.exit(0)


for path in sorted(changed):
    print(path)
