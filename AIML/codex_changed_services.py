#!/usr/bin/env python3

import subprocess
import sys


def run_git(*args):
    result = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


base = sys.argv[1] if len(sys.argv) > 1 else "start"

try:
    merge_base = run_git("merge-base", base, "HEAD")
except subprocess.CalledProcessError:
    print(f"Unable to determine merge base against {base}", file=sys.stderr)
    sys.exit(1)

try:
    output = run_git(
        "diff",
        "--name-only",
        merge_base,
        "HEAD",
        "--",
        "app/",
        "migrations/",
    )
except subprocess.CalledProcessError as exc:
    print(exc.stderr, file=sys.stderr)
    sys.exit(exc.returncode)

files = [line for line in output.splitlines() if line.strip()]

if not files:
    print("NO_CHANGED_APPLICATION_FILES")
    sys.exit(0)

for path in files:
    print(path)
