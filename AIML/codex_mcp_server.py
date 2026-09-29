from pathlib import Path
import os
import sqlite3
import uuid

from mcp.server.fastmcp import FastMCP


server = FastMCP("taskflow-ops")

REPO_ROOT = Path(
    os.environ.get("TASKFLOW_REPO", Path.cwd())
).resolve()

DB_PATH = Path(
    os.environ.get("TASKFLOW_DB", REPO_ROOT / "taskflow.db")
).resolve()

REQUESTS = {}


def connect():
    return sqlite3.connect(DB_PATH)


@server.tool()
def list_tasks(status: str | None = None) -> list[dict]:
    """List TaskFlow tasks. Optionally filter by status."""
    conn = connect()
    conn.row_factory = sqlite3.Row

    try:
        if status:
            rows = conn.execute(
                "SELECT id, title, status, priority_score "
                "FROM tasks WHERE status = ? ORDER BY id",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, status, priority_score "
                "FROM tasks ORDER BY id"
            ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


@server.tool()
def get_task(task_id: int) -> dict:
    """Read one TaskFlow task by ID."""
    conn = connect()
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            "SELECT id, title, status, priority_score "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            return {
                "found": False,
                "task_id": task_id,
            }

        return {
            "found": True,
            "task": dict(row),
        }
    finally:
        conn.close()


@server.tool()
def pending_migrations() -> dict:
    """Report migration files known in the repository."""
    migrations_dir = REPO_ROOT / "migrations"

    migrations = sorted(
        path.name
        for path in migrations_dir.glob("*.py")
        if path.name != "__init__.py"
    )

    return {
        "repository": str(REPO_ROOT),
        "migrations": migrations,
    }


@server.tool()
def request_migration(direction: str) -> dict:
    """Create a migration request. This does not execute a migration."""

    if direction not in {"up", "down"}:
        return {
            "created": False,
            "error": "direction must be 'up' or 'down'",
        }

    request_id = uuid.uuid4().hex[:8]

    REQUESTS[request_id] = {
        "direction": direction,
        "status": "pending",
    }

    return {
        "created": True,
        "request_id": request_id,
        "status": "pending",
        "message": "Migration request created. No migration was executed.",
    }


@server.tool()
def check_migration_status(request_id: str) -> dict:
    """Read the status of a migration request."""

    request = REQUESTS.get(request_id)

    if request is None:
        return {
            "found": False,
            "request_id": request_id,
        }

    return {
        "found": True,
        "request_id": request_id,
        **request,
    }


if __name__ == "__main__":
    server.run(transport="stdio")
