"""Resource Lease (Chapter 34).

An exclusive, time-bound claim on a shared resource, acquired through one
atomic operation. This SQLite version demonstrates the same
compare-and-set contract a production system would get from Redis
(SET NX PX) or a database's conditional write; swap the backend, keep
the interface.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone


class LeaseDenied(Exception):
    """Raised when a resource is already held by someone else's live lease."""


class LeaseStore:
    def __init__(self, path: str = ":memory:"):
        # check_same_thread=False: this store is explicitly meant to be
        # hammered from multiple threads (see test_lease_concurrency.py).
        # Safety comes from BEGIN IMMEDIATE below, not from single-threaded use.
        self._conn = sqlite3.connect(
            path, timeout=30.0, check_same_thread=False, uri=path.startswith("file:")
        )
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leases (
                resource_id TEXT PRIMARY KEY,
                holder_id TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def acquire(self, resource_id: str, holder_id: str, ttl_seconds: int) -> bool:
        """Atomic acquire: succeeds if unheld or the existing lease expired.

        BEGIN IMMEDIATE takes SQLite's write lock before the SELECT runs,
        not after the first write like the default deferred transaction
        does. Without it, two threads' SELECTs can both see "unheld"
        before either one writes -- the exact check-then-act race this
        chapter exists to close, discovered here by a real concurrency
        test (see test_lease_concurrency.py) rather than caught in review.
        """
        now = datetime.now(timezone.utc)
        # Retry SQLITE_LOCKED / SQLITE_BUSY under real contention: busy_timeout
        # covers most of this, but shared-cache mode in particular can raise
        # "database table is locked" in a way that doesn't always honor it.
        # A production deployment on Postgres or Redis wouldn't need this;
        # it's here because this reference store is genuinely meant to be
        # hit by concurrent callers, and discovering that the hard way
        # under a real stress test (see test_lease_concurrency.py) is the
        # point of building this instead of only describing it in prose.
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(5):
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                try:
                    row = self._conn.execute(
                        "SELECT expires_at FROM leases WHERE resource_id = ?", (resource_id,)
                    ).fetchone()
                    if row is not None and datetime.fromisoformat(row[0]) > now:
                        self._conn.rollback()
                        return False
                    expires = now + timedelta(seconds=ttl_seconds)
                    self._conn.execute(
                        "INSERT INTO leases (resource_id, holder_id, expires_at) VALUES (?, ?, ?) "
                        "ON CONFLICT(resource_id) DO UPDATE SET holder_id = excluded.holder_id, "
                        "expires_at = excluded.expires_at",
                        (resource_id, holder_id, expires.isoformat()),
                    )
                    self._conn.commit()
                    return True
                except BaseException:
                    self._conn.rollback()
                    raise
            except sqlite3.OperationalError as exc:
                last_error = exc
                time.sleep(0.01 * (attempt + 1))
        raise last_error

    def release(self, resource_id: str, holder_id: str) -> None:
        """Release only if still held by this holder, so a lease that already
        expired and was reacquired by someone else is never released out
        from under them."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "DELETE FROM leases WHERE resource_id = ? AND holder_id = ?",
                (resource_id, holder_id),
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()


def with_lease(store: LeaseStore, resource_id: str, holder_id: str, ttl_seconds: int, fn):
    """Run fn() only while holding the lease; always release afterward."""
    if not store.acquire(resource_id, holder_id, ttl_seconds):
        raise LeaseDenied(f"{resource_id} is held by another task")
    try:
        return fn()
    finally:
        store.release(resource_id, holder_id)
