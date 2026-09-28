#!/usr/bin/env python3

import json
from pathlib import Path
import re
import sys


REPORT = Path("RELEASE_REPORT.md")


def block(reason):
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": reason,
            }
        )
    )
    sys.exit(0)


def allow():
    print("{}")
    sys.exit(0)


if not REPORT.exists():
    block(
        "RELEASE_REPORT.md is missing. "
        "Run the production-readiness Skill and create the report "
        "before completing this turn."
    )


text = REPORT.read_text(encoding="utf-8")


expected_steps = list(range(22, 30))

for step in expected_steps:
    pattern = rf"(?m)^{step}\.\s+.+?:\s+(PASS|FAIL|WAIVED)\b"

    if not re.search(pattern, text):
        block(
            f"RELEASE_REPORT.md is incomplete or malformed. "
            f"Required checklist entry {step} is missing."
        )


verdict_match = re.search(
    r"(?m)^VERDICT:\s+(READY|NOT READY)\s*$",
    text,
)

if not verdict_match:
    block(
        "RELEASE_REPORT.md does not contain a valid final verdict. "
        "Expected VERDICT: READY or VERDICT: NOT READY."
    )


statuses = {}

for step in expected_steps:
    match = re.search(
        rf"(?m)^{step}\.\s+.+?:\s+(PASS|FAIL|WAIVED)\b",
        text,
    )

    statuses[step] = match.group(1)


verdict = verdict_match.group(1)


if verdict == "READY":
    failed = [
        str(step)
        for step, status in statuses.items()
        if status == "FAIL"
    ]

    if failed:
        block(
            "RELEASE_REPORT.md declares READY but contains FAIL "
            "status for checklist step(s): "
            + ", ".join(failed)
            + ". Fix the underlying issue or change the verdict "
              "to NOT READY."
        )


allow()
