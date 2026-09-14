"""Durable Task Graph (Chapter 22).

Persists each step's status so any process can resume a plan that was
interrupted mid-execution, and pairs with Chapter 20's idempotency for
steps that might get retried after an ambiguous crash.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable


@dataclass
class Step:
    name: str
    execute: Callable[[], None]


class TaskStore:
    def __init__(self, path: str = ":memory:"):
        # Same reasoning as Ledger: shared across every request behind a
        # real ASGI server, so genuinely multi-threaded, not just in a
        # single-threaded test or CLI call.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_steps (
                task_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (task_id, step_name)
            )
            """
        )
        self._conn.commit()

    def set_status(self, task_id: str, step_name: str, status: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO task_steps (task_id, step_name, status) VALUES (?, ?, ?) "
                "ON CONFLICT(task_id, step_name) DO UPDATE SET status = excluded.status",
                (task_id, step_name, status),
            )

    def get_status(self, task_id: str, step_name: str) -> str | None:
        row = self._conn.execute(
            "SELECT status FROM task_steps WHERE task_id = ? AND step_name = ?",
            (task_id, step_name),
        ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._conn.close()


def run_step(store: TaskStore, task_id: str, step: Step) -> None:
    store.set_status(task_id, step.name, "in_progress")
    step.execute()
    store.set_status(task_id, step.name, "completed")


def resume(store: TaskStore, task_id: str, plan: list[Step]) -> list[str]:
    """Run every step not already completed. Returns the names of steps
    actually executed on this call, so callers/tests can see what resuming
    skipped versus what it redid."""
    ran = []
    for step in plan:
        if store.get_status(task_id, step.name) == "completed":
            continue
        run_step(store, task_id, step)
        ran.append(step.name)
    return ran
