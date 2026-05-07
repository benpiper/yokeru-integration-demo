import sqlite3

from src.db import CallBuffer
from src.schemas import YokeruCallTask


def test_insert_and_list_unsynced(tmp_path):
    buf = CallBuffer(db_path=str(tmp_path / "x.db"))
    task = YokeruCallTask(patient_id="1", phone="555")
    buf.insert_pending("cid-1", task)

    rows = buf.list_unsynced()
    assert len(rows) == 1
    assert rows[0][0] == "cid-1"


def test_mark_delivered_removes_from_unsynced(tmp_path):
    buf = CallBuffer(db_path=str(tmp_path / "x.db"))
    buf.insert_pending("cid-1", YokeruCallTask(patient_id="1", phone="555"))
    buf.mark_delivered("cid-1")
    assert buf.list_unsynced() == []


def test_mark_permanent_failure_persists_reason(tmp_path):
    db_path = str(tmp_path / "x.db")
    buf = CallBuffer(db_path=db_path)
    buf.insert_pending("cid-1", YokeruCallTask(patient_id="1", phone="555"))
    buf.mark_permanent_failure("cid-1", "no phone on file")

    assert buf.list_unsynced() == []
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, reason FROM call_buffer WHERE correlation_id=?",
            ("cid-1",),
        ).fetchone()
    assert row == ("FAILED_PERMANENT", "no phone on file")


def test_record_webhook_is_idempotent(tmp_path):
    buf = CallBuffer(db_path=str(tmp_path / "x.db"))
    assert buf.record_webhook("evt-1", "call.completed", "{}") is True
    assert buf.record_webhook("evt-1", "call.completed", "{}") is False


def test_record_call_outcome_updates_existing_row(tmp_path):
    db_path = str(tmp_path / "x.db")
    buf = CallBuffer(db_path=db_path)
    buf.insert_pending("cid-out", YokeruCallTask(patient_id="1", phone="555"))

    assert buf.record_call_outcome("cid-out", "completed") is True
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT outcome, completed_at FROM call_buffer WHERE correlation_id=?",
            ("cid-out",),
        ).fetchone()
    assert row[0] == "completed"
    assert row[1] is not None  # completed_at populated


def test_record_call_outcome_returns_false_for_unknown_correlation(tmp_path):
    buf = CallBuffer(db_path=str(tmp_path / "x.db"))
    assert buf.record_call_outcome("never-dispatched", "completed") is False
