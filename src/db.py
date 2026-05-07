import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from .schemas import YokeruCallTask

SCHEMA = """
CREATE TABLE IF NOT EXISTS call_buffer (
    correlation_id TEXT PRIMARY KEY,
    patient_id     TEXT NOT NULL,
    payload        TEXT NOT NULL,
    status         TEXT NOT NULL,
    synced         INTEGER NOT NULL DEFAULT 0,
    attempts       INTEGER NOT NULL DEFAULT 0,
    reason         TEXT,
    outcome        TEXT,
    completed_at   TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_call_buffer_correlation ON call_buffer(correlation_id);

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id     TEXT PRIMARY KEY,
    event_type   TEXT NOT NULL,
    received_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    payload      TEXT NOT NULL
);
"""

# Maps inbound webhook event types to terminal outcomes recorded on the
# originating call_buffer row. New event types must be added here explicitly.
EVENT_TYPE_TO_OUTCOME = {
    "call.completed": "completed",
    "call.failed": "failed",
    "call.no_answer": "no_answer",
}


class CallBuffer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            # Lightweight migration: add columns introduced after v0.1 to
            # existing on-disk DBs. ALTER TABLE ADD COLUMN is the only schema
            # change SQLite can apply in-place safely.
            existing = {row[1] for row in conn.execute("PRAGMA table_info(call_buffer)")}
            for col in ("reason", "outcome", "completed_at"):
                if col not in existing:
                    conn.execute(f"ALTER TABLE call_buffer ADD COLUMN {col} TEXT")

    def insert_pending(self, correlation_id: str, task: YokeruCallTask) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO call_buffer "
                "(correlation_id, patient_id, payload, status, synced) "
                "VALUES (?, ?, ?, 'PENDING', 0)",
                (correlation_id, task.patient_id, task.model_dump_json()),
            )

    def mark_delivered(self, correlation_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE call_buffer SET status='DELIVERED', synced=1, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE correlation_id=?",
                (correlation_id,),
            )

    def mark_permanent_failure(self, correlation_id: str, reason: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE call_buffer SET status='FAILED_PERMANENT', synced=1, reason=?, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE correlation_id=?",
                (reason, correlation_id),
            )

    def increment_attempts(self, correlation_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE call_buffer SET attempts=attempts+1, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE correlation_id=?",
                (correlation_id,),
            )

    def list_unsynced(self) -> list[tuple[str, str, str]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT correlation_id, patient_id, payload "
                "FROM call_buffer WHERE synced=0 AND status='PENDING'"
            )
            return cur.fetchall()

    def record_call_outcome(self, correlation_id: str, outcome: str) -> bool:
        """Stamp a terminal outcome from an inbound webhook onto the originating
        call_buffer row. Returns True if a row was updated, False if no matching
        correlation_id exists (e.g., webhook for a call we never dispatched)."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE call_buffer SET outcome=?, "
                "completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE correlation_id=?",
                (outcome, correlation_id),
            )
            return cur.rowcount > 0

    def record_webhook(self, event_id: str, event_type: str, payload: str) -> bool:
        """Insert a webhook event. Returns False if already seen (idempotent replay)."""
        with self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO webhook_events (event_id, event_type, payload) VALUES (?, ?, ?)",
                    (event_id, event_type, payload),
                )
                return True
            except sqlite3.IntegrityError:
                return False
