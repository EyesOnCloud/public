#!/usr/bin/env python3

from pathlib import Path
import re
import sys


changed_files = sys.argv[1:]

if not changed_files:
    print("NO_CHANGED_FILES_PROVIDED")
    sys.exit(0)

tests_dir = Path("tests")

if not tests_dir.exists():
    print("TEST_DIRECTORY_NOT_FOUND")
    sys.exit(1)

affected = set()

for changed in changed_files:
    path = Path(changed)

    if path.suffix != ".py":
        continue

    if "app" not in path.parts:
        continue

    module = path.stem

    patterns = [
        rf"\bimport\s+app\.{re.escape(module)}\b",
        rf"\bfrom\s+app\.{re.escape(module)}\s+import\b",
        rf"\bfrom\s+app\s+import\s+.*\b{re.escape(module)}\b",
    ]

    for test_file in tests_dir.rglob("test_*.py"):
        text = test_file.read_text(encoding="utf-8")

        if any(re.search(pattern, text) for pattern in patterns):
            affected.add(str(test_file))

if not affected:
    print("NO_AFFECTED_TESTS_FOUND")
    sys.exit(0)

for test in sorted(affected):
    print(test)
