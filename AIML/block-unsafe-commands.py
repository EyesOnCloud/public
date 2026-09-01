#!/usr/bin/env python3
import json, re, sys

BLOCKED_PATTERNS = [
    (r"\bsqlite3\b.*taskflow\.db",
     "Direct sqlite3 CLI access to taskflow.db bypasses the migration "
     "runner. Use the taskflow-ops MCP server's migration tools instead."),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b",
     "Recursive forced delete is blocked in this repo."),
    (r"\bgit\s+push\b.*(--force\b|-f\b)",
     "Force-pushing is blocked in this repo."),
]

def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("could not parse tool call input; blocking to be safe", file=sys.stderr)
        sys.exit(2)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    for pattern, reason in BLOCKED_PATTERNS:
        if re.search(pattern, command):
            print(f"BLOCKED: {reason}\nCommand was: {command}", file=sys.stderr)
            sys.exit(2)
    sys.exit(0)

if __name__ == "__main__":
    main()
