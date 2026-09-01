import json
import os
import secrets
import sqlite3
import sys
import time

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

REPO_ROOT = os.environ.get("TASKFLOW_REPO", os.getcwd())
DB_PATH = os.environ.get("TASKFLOW_DB", os.path.join(REPO_ROOT, "taskflow.db"))
REQUESTS_PATH = os.path.join(REPO_ROOT, ".taskflow-ops", "change_requests.json")

os.makedirs(os.path.dirname(REQUESTS_PATH), exist_ok=True)

mcp = MCPServer("taskflow-ops")


# ---------------------------------------------------------------------------
# Tiny local store for pending/approved requests. A file, not a database,
# on purpose -- this server's own bookkeeping should not depend on the
# same database its tools operate on.
# ---------------------------------------------------------------------------

def _load_requests():
    if not os.path.exists(REQUESTS_PATH):
        return {}
    with open(REQUESTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_requests(requests):
    with open(REQUESTS_PATH, "w", encoding="utf-8") as f:
        json.dump(requests, f, indent=2)


def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Read-only resources -- no approval needed, because nothing here writes.
# ---------------------------------------------------------------------------

@mcp.resource("taskflow://tasks")
def tasks_resource() -> str:
    """Every task currently in the TaskFlow database, as JSON."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        return json.dumps([dict(r) for r in rows], indent=2)
    finally:
        conn.close()


@mcp.resource("taskflow://schema-migrations")
def schema_migrations_resource() -> str:
    """Which migrations have actually been applied to this database."""
    conn = _get_connection()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        rows = conn.execute("SELECT version, applied_at FROM schema_migrations").fetchall()
        return json.dumps([dict(r) for r in rows], indent=2)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Narrow, typed, read-only tools.
# ---------------------------------------------------------------------------

@mcp.tool()
def list_tasks(status: str | None = None) -> list[dict]:
    """List tasks, optionally filtered by status. Read-only."""
    conn = _get_connection()
    try:
        if status:
            rows = conn.execute("SELECT * FROM tasks WHERE status = ?", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@mcp.tool()
def get_task(task_id: int) -> dict:
    """Fetch one task by id. Read-only."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else {"error": f"no task with id {task_id}"}
    finally:
        conn.close()


@mcp.tool()
def pending_migrations() -> dict:
    """Report which migration modules exist versus which have been applied.
    Read-only -- this only reports state, it never runs anything."""
    sys.path.insert(0, os.path.join(REPO_ROOT, "migrations"))
    from migrations import runner  # local import: repo-specific path

    conn = _get_connection()
    try:
        applied = sorted(runner.applied_versions(conn))
        defined = list(runner.MIGRATION_MODULES)
        return {
            "defined": defined,
            "applied": applied,
            "pending": [m for m in defined if m not in applied],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The gated write path: request -> (human approves out-of-band) -> apply.
# ---------------------------------------------------------------------------

@mcp.tool()
def request_migration(direction: str, target_version: str | None = None) -> dict:
    """Request permission to run a migration. direction must be 'up' or
    'down'. This does NOT run anything -- it only creates a pending
    request and returns its id. A human must approve it out-of-band
    before apply_migration() will do anything.
    """
    if direction not in ("up", "down"):
        return {"error": "direction must be 'up' or 'down'"}

    requests = _load_requests()
    request_id = secrets.token_hex(4)
    code = f"{secrets.randbelow(900000) + 100000}"  # 6-digit code

    requests[request_id] = {
        "direction": direction,
        "target_version": target_version,
        "status": "pending",
        "created_at": time.time(),
        # The code itself is stored here for comparison, but this file is
        # never exposed through any tool result -- only approve_migration()
        # reads it internally, and only to compare against what a human
        # supplies.
        "_code": code,
    }
    _save_requests(requests)

    # This is the ONLY place the code is ever emitted, and it goes to this
    # process's own stderr -- the terminal of whoever launched this MCP
    # server, not to the calling agent.
    print(
        f"\n[taskflow-ops] Migration request {request_id} ({direction}"
        f"{' -> ' + target_version if target_version else ''}) needs approval.\n"
        f"[taskflow-ops] Approval code: {code}\n",
        file=sys.stderr,
        flush=True,
    )

    return {
        "request_id": request_id,
        "status": "pending",
        "message": (
            "Migration request created. This tool cannot approve its own "
            "request -- ask a human with access to this server's terminal "
            "for the approval code, then call approve_migration()."
        ),
    }


@mcp.tool()
def check_migration_status(request_id: str) -> dict:
    """Check a request's status. Never returns the approval code."""
    requests = _load_requests()
    req = requests.get(request_id)
    if not req:
        return {"error": f"no request with id {request_id}"}
    return {
        "request_id": request_id,
        "direction": req["direction"],
        "target_version": req.get("target_version"),
        "status": req["status"],
    }


@mcp.tool()
def approve_migration(request_id: str, code: str) -> dict:
    """Approve a pending migration request. Requires the exact approval
    code that was printed to the server's own terminal -- a value the
    calling agent has no way to obtain on its own."""
    requests = _load_requests()
    req = requests.get(request_id)
    if not req:
        return {"error": f"no request with id {request_id}"}
    if req["status"] != "pending":
        return {"error": f"request {request_id} is already {req['status']}"}
    if code != req["_code"]:
        return {"error": "incorrect approval code"}

    req["status"] = "approved"
    _save_requests(requests)
    return {"request_id": request_id, "status": "approved"}


@mcp.tool()
def apply_migration(request_id: str) -> dict:
    """Actually run the migration -- but only if the request has been
    approved. Refuses (fail-closed) for any other status, including
    'pending' and any status this server doesn't recognize."""
    requests = _load_requests()
    req = requests.get(request_id)
    if not req:
        return {"error": f"no request with id {request_id}"}
    if req["status"] != "approved":
        # Fail closed: anything other than an explicit "approved" refuses.
        return {
            "error": f"cannot apply -- request status is '{req['status']}', not 'approved'"
        }

    sys.path.insert(0, os.path.join(REPO_ROOT, "migrations"))
    from migrations import runner

    conn = _get_connection()
    try:
        if req["direction"] == "up":
            runner.migrate_up(conn)
        else:
            runner.migrate_down(conn, target_version=req.get("target_version"))
    finally:
        conn.close()

    req["status"] = "applied"
    req["applied_at"] = time.time()
    _save_requests(requests)
    return {"request_id": request_id, "status": "applied"}


if __name__ == "__main__":
    mcp.run()
