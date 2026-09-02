"""Confirms app/task_service.py's create_task() never logs personal
data -- Defect #6. Uses pytest's caplog fixture to inspect the real
log records emitted, not just the code that produced them.
"""
import logging

from app import db, task_service


def test_create_task_log_line_excludes_assignee_email_and_description(tmp_path, caplog):
    conn = db.get_connection(str(tmp_path / "log_test.db"))
    conn.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, "
        "description TEXT, assignee_email TEXT, status TEXT, idempotency_key TEXT)"
    )

    sensitive_email = "very-specific-person@example.com"
    sensitive_description = "my social security number is 000-00-0000"

    with caplog.at_level(logging.INFO, logger="taskflow.tasks"):
        task_service.create_task(
            conn,
            title="Reset my password",
            description=sensitive_description,
            assignee_email=sensitive_email,
        )

    all_log_text = "\n".join(record.getMessage() for record in caplog.records)

    assert sensitive_email not in all_log_text, (
        "Defect #6: assignee_email appeared in a log record"
    )
    assert sensitive_description not in all_log_text, (
        "Defect #6: description appeared in a log record"
    )
    # The fix should still log SOMETHING useful (id, title) -- this
    # isn't a test that logging should be silent, just that it should
    # be safe. Confirm the log line wasn't simply deleted.
    assert any("Reset my password" in record.getMessage() for record in caplog.records) or \
           any("task created" in record.getMessage() for record in caplog.records), (
        "expected a log record confirming task creation, just without the sensitive fields"
    )
