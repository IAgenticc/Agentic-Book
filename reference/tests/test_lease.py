import time

import pytest

from sre_agent.lease import LeaseDenied, LeaseStore, with_lease


def test_acquire_succeeds_when_unheld():
    store = LeaseStore()
    assert store.acquire("checkout", "task-a", ttl_seconds=60) is True


def test_second_acquire_fails_while_first_still_live():
    store = LeaseStore()
    store.acquire("checkout", "task-a", ttl_seconds=60)
    assert store.acquire("checkout", "task-b", ttl_seconds=60) is False


def test_acquire_succeeds_again_after_expiry():
    # Generous margin (20x, not 1.2x) between ttl and sleep: a tight
    # margin here is a real source of flakiness under scheduler jitter,
    # not just a theoretical concern -- see test_circuit_breaker.py's
    # matching fix, found the same way.
    store = LeaseStore()
    store.acquire("checkout", "task-a", ttl_seconds=0.01)
    time.sleep(0.2)
    assert store.acquire("checkout", "task-b", ttl_seconds=60) is True


def test_release_only_by_current_holder():
    store = LeaseStore()
    store.acquire("checkout", "task-a", ttl_seconds=60)
    store.release("checkout", "task-b")  # not the holder, should not release
    assert store.acquire("checkout", "task-c", ttl_seconds=60) is False
    store.release("checkout", "task-a")
    assert store.acquire("checkout", "task-c", ttl_seconds=60) is True


def test_with_lease_denies_concurrent_work_and_always_releases():
    store = LeaseStore()

    def work():
        # while inside, a second task must be denied
        with pytest.raises(LeaseDenied):
            store_denied_check()
        return "done"

    def store_denied_check():
        if not store.acquire("checkout", "task-b", ttl_seconds=60):
            raise LeaseDenied("checkout is held by another task")

    result = with_lease(store, "checkout", "task-a", ttl_seconds=60, fn=work)
    assert result == "done"
    # released afterward, so a fresh acquire now succeeds
    assert store.acquire("checkout", "task-c", ttl_seconds=60) is True
