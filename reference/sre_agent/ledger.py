"""Audit Ledger (Chapter 29).

A durable, queryable-by-task-id record of every consequential decision.
Backed by SQLite so it survives the process, and one connection per
Ledger instance keeps this simple to reason about and test.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class LedgerEntry:
    task_id: str
    timestamp: str
    event_type: str
    details: dict


class Ledger:
    def __init__(self, path: str = ":memory:"):
        # check_same_thread=False + busy_timeout: a Ledger instance built
        # once at app startup and shared across every request is genuinely
        # used from a different thread per request under a real ASGI
        # server's threadpool, not just in a single-threaded test or CLI
        # call. See Appendix C for how running this behind FastAPI
        # surfaced that.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def write(self, task_id: str, event_type: str, details: dict) -> None:
        self._conn.execute(
            "INSERT INTO ledger (task_id, timestamp, event_type, details) VALUES (?, ?, ?, ?)",
            (task_id, datetime.now(timezone.utc).isoformat(), event_type, json.dumps(details)),
        )
        self._conn.commit()

    def for_task(self, task_id: str) -> list[LedgerEntry]:
        rows = self._conn.execute(
            "SELECT task_id, timestamp, event_type, details FROM ledger "
            "WHERE task_id = ? ORDER BY id ASC",
            (task_id,),
        ).fetchall()
        return [
            LedgerEntry(task_id=r[0], timestamp=r[1], event_type=r[2], details=json.loads(r[3]))
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
