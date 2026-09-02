"""Characterization tests for app/priority.py -- Defect #5.

Every branch of calculate_priority() is pinned by a test computed from
the function's actual output. This does NOT invent a justification for
the days_overdue >= 3 threshold -- that origin is still undocumented,
which is the honest state of the code. What this fixes is the missing
safety net: any future change to this behavior is now a visible,
deliberate decision instead of a silent accident.
"""
from app.priority import calculate_priority


def test_open_task_zero_days_overdue_is_normal():
    assert calculate_priority(days_overdue=0, status="open") == "normal"


def test_open_task_under_threshold_is_normal():
    assert calculate_priority(days_overdue=2, status="open") == "normal"


def test_open_task_at_threshold_is_high():
    assert calculate_priority(days_overdue=3, status="open") == "high"


def test_open_task_well_past_threshold_is_high():
    assert calculate_priority(days_overdue=30, status="open") == "high"


def test_negative_days_overdue_is_normal():
    assert calculate_priority(days_overdue=-1, status="open") == "normal"


def test_in_progress_task_follows_same_threshold_as_open():
    assert calculate_priority(days_overdue=1, status="in_progress") == "normal"
    assert calculate_priority(days_overdue=3, status="in_progress") == "high"


def test_done_task_is_always_normal_regardless_of_days_overdue():
    assert calculate_priority(days_overdue=0, status="done") == "normal"
    assert calculate_priority(days_overdue=99, status="done") == "normal"
