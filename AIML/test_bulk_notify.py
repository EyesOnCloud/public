"""Real HTTP-level test for the bulk-notify rate limit -- Defect #3.
Starts the actual TaskFlowHandler on a real socket and hits it with a
real HTTP request, rather than calling the handler method directly --
this is an HTTP endpoint, so the test goes through HTTP.
"""
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

from app import db, main, task_service
from migrations import runner


def _start_server(db_path):
    # app/db.py's get_connection() reads the module-level DB_PATH at
    # call time, resolved once from TASKFLOW_DB at import time -- by
    # the time this test runs, app.db is already imported, so setting
    # the env var here would do nothing. Patch the module attribute
    # directly instead; get_connection() looks it up fresh each call.
    db.DB_PATH = db_path
    server = HTTPServer(("127.0.0.1", 0), main.TaskFlowHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_bulk_notify_caps_at_max_notifies_per_request(tmp_path):
    db_path = str(tmp_path / "bulk_test.db")
    conn = db.get_connection(db_path)
    runner.migrate_up(conn)

    # Seed more "done" tasks than the cap.
    total_tasks = main.TaskFlowHandler.MAX_NOTIFIES_PER_REQUEST + 10
    for i in range(total_tasks):
        task_id = task_service.create_task(conn, f"task {i}", "d", "a@b.com")
        task_service.update_task(conn, task_id, status="done")
    conn.close()

    server, port = _start_server(db_path)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/tasks/bulk-notify", data=b"{}", method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read())

        assert body["notified"] == main.TaskFlowHandler.MAX_NOTIFIES_PER_REQUEST, (
            f"expected exactly {main.TaskFlowHandler.MAX_NOTIFIES_PER_REQUEST} notify "
            f"attempts, got {body['notified']} -- Defect #3: no cap on bulk-notify"
        )
        assert body["skipped_due_to_rate_limit"] == 10, (
            "expected the 10 tasks over the cap to be reported as skipped, not silently dropped"
        )
    finally:
        server.shutdown()
