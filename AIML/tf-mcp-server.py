import json
import os
import sqlite3
import sys

from mcp.server.fastmcp import FastMCP

REPO_ROOT = os.environ.get("TASKFLOW_REPO", os.getcwd())
DB_PATH = os.environ.get("TASKFLOW_DB", os.path.join(REPO_ROOT, "taskflow.db"))

mcp = FastMCP("taskflow-ops")


def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.resource("taskflow://tasks")
def tasks_resource() -> str:
    """Every task currently in the TaskFlow database, as JSON."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        return json.dumps([dict(r) for r in rows], indent=2)
    finally:
        conn.close()


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
def pending_migrations() -> dict:
    """Report which migrations exist versus which are applied. Read-only."""
    sys.path.insert(0, os.path.join(REPO_ROOT, "migrations"))
    from migrations import runner

    conn = _get_connection()
    try:
        applied = sorted(runner.applied_versions(conn))
        defined = list(runner.MIGRATION_MODULES)
        return {"defined": defined, "applied": applied, "pending": [m for m in defined if m not in applied]}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
