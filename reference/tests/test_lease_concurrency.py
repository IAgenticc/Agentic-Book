"""Real concurrency test for the Resource Lease (Chapter 34).

Every other lease test calls acquire() sequentially, which never actually
exercises the race the whole pattern exists to prevent. This test fires
many real threads at the same resource simultaneously and asserts exactly
one of them wins, which is the actual claim Chapter 34 makes.

Each thread gets its OWN LeaseStore (its own sqlite3 connection) pointed
at the same on-disk database file. That matters twice over:

  - A single sqlite3.Connection object can only have one transaction open
    at a time, so sharing one Connection across threads would test
    Python's own single-connection transaction tracking, not the
    database-level locking this pattern actually relies on.
  - A real file (not a shared-cache in-memory database) is what gives
    ordinary SQLITE_BUSY + busy_timeout semantics. Shared-cache mode has
    its own SQLITE_LOCKED_SHAREDCACHE behavior that doesn't always honor
    busy_timeout the same way -- discovered here, the hard way, the first
    time this test was written; see lease.py's retry loop in acquire().
"""
import tempfile
import threading
from pathlib import Path

from sre_agent.lease import LeaseStore


def test_exactly_one_thread_wins_a_true_concurrent_race():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "lease_race.db")
        LeaseStore(db_path).close()  # create the schema once up front

        winners: list[str] = []
        lock = threading.Lock()

        def try_acquire(holder_id: str) -> None:
            store = LeaseStore(db_path)  # each caller: its own connection
            try:
                if store.acquire("checkout", holder_id, ttl_seconds=60):
                    with lock:
                        winners.append(holder_id)
            finally:
                store.close()

        threads = [threading.Thread(target=try_acquire, args=(f"task-{i}",)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(winners) == 1, f"expected exactly one winner, got {winners}"
