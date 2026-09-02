"""Process each incident once (FR5).

An in-memory set is allowed by the brief, but SQLite buys two things cheaply:
* an **atomic** claim (`INSERT` on a PRIMARY KEY) — a check-then-add set races when two
  deliveries arrive together;
* **restart safety** with a status per incident, so a crash mid-write-back doesn't strand
  the incident (a `failed` row can be re-claimed and retried).

One local file, standard-library only.
"""

import sqlite3
import time
from functools import lru_cache

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_incidents (
    incident_sys_id TEXT PRIMARY KEY,
    number          TEXT,
    status          TEXT NOT NULL,   -- 'processing' | 'done' | 'failed'
    decision        TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
"""


class Idempotency:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5, isolation_level=None)  # autocommit
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def claim(self, incident_sys_id: str, number: str) -> bool:
        """Try to take ownership of an incident.

        Returns True if this caller now owns it (first time, or re-claiming a previously
        `failed` one), False if it is already `processing` or `done`.
        """
        now = time.time()
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO processed_incidents "
                    "(incident_sys_id, number, status, created_at, updated_at) "
                    "VALUES (?, ?, 'processing', ?, ?)",
                    (incident_sys_id, number, now, now),
                )
                return True
            except sqlite3.IntegrityError:
                cur = conn.execute(
                    "UPDATE processed_incidents SET status='processing', updated_at=? "
                    "WHERE incident_sys_id=? AND status='failed'",
                    (now, incident_sys_id),
                )
                return cur.rowcount > 0

    def complete(self, incident_sys_id: str, decision: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE processed_incidents SET status='done', decision=?, updated_at=? "
                "WHERE incident_sys_id=?",
                (decision, time.time(), incident_sys_id),
            )

    def fail(self, incident_sys_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE processed_incidents SET status='failed', updated_at=? "
                "WHERE incident_sys_id=?",
                (time.time(), incident_sys_id),
            )

    def status(self, incident_sys_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM processed_incidents WHERE incident_sys_id=?",
                (incident_sys_id,),
            ).fetchone()
        return row[0] if row else None


@lru_cache
def _idempotency_for(db_path: str) -> Idempotency:
    return Idempotency(db_path)


def get_idempotency() -> Idempotency:
    from app.config import get_settings

    return _idempotency_for(get_settings().dedup_db_path)
