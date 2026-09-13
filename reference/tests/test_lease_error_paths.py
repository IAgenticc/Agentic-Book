"""Targeted tests for lease.py's error-handling branches, which a
normal-path test never exercises: retry exhaustion under sustained lock
contention, and rollback when something other than lock contention fails
mid-transaction.

sqlite3.Connection is an immutable C type -- it can't be monkeypatched,
at either the instance or the class level. A thin proxy that forwards
everything except execute() is the correct way to inject a controlled
failure here.
"""
import sqlite3

import pytest

from sre_agent.lease import LeaseStore


class _FlakyConnProxy:
    """Forwards everything to a real connection except execute(), which
    can be made to fail on demand for statements matching a prefix."""

    def __init__(self, real_conn, fail_sql_prefix: str, exc: Exception):
        self._real = real_conn
        self._fail_sql_prefix = fail_sql_prefix
        self._exc = exc

    def execute(self, sql, *args, **kwargs):
        if sql.startswith(self._fail_sql_prefix):
            raise self._exc
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_acquire_raises_after_exhausting_retries_on_sustained_lock_contention():
    store = LeaseStore()
    store._conn = _FlakyConnProxy(
        store._conn, fail_sql_prefix="BEGIN", exc=sqlite3.OperationalError("database table is locked")
    )
    with pytest.raises(sqlite3.OperationalError):
        store.acquire("checkout", "task-a", ttl_seconds=60)


def test_acquire_rolls_back_and_reraises_on_an_unexpected_error():
    store = LeaseStore()
    real_conn = store._conn
    store._conn = _FlakyConnProxy(real_conn, fail_sql_prefix="INSERT", exc=ValueError("simulated corruption"))

    with pytest.raises(ValueError):
        store.acquire("checkout", "task-a", ttl_seconds=60)

    store._conn = real_conn  # remove the proxy, use the real connection again
    # rollback actually happened: a fresh acquire should succeed as if
    # the failed attempt never wrote anything.
    assert store.acquire("checkout", "task-b", ttl_seconds=60) is True


def test_release_rolls_back_and_reraises_on_an_unexpected_error():
    store = LeaseStore()
    store.acquire("checkout", "task-a", ttl_seconds=60)
    real_conn = store._conn
    store._conn = _FlakyConnProxy(real_conn, fail_sql_prefix="DELETE", exc=ValueError("simulated failure"))

    with pytest.raises(ValueError):
        store.release("checkout", "task-a")

    store._conn = real_conn
    # the lease is still intact since the delete was rolled back
    assert store.acquire("checkout", "task-b", ttl_seconds=60) is False
