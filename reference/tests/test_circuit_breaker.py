import time

import pytest

from sre_agent.circuit_breaker import CircuitBreaker, CircuitOpenError


def failing():
    raise RuntimeError("dependency down")


def succeeding():
    return "ok"


def test_closed_by_default_and_passes_through_success():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
    assert cb.call(succeeding) == "ok"
    assert cb.state == "closed"


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(failing)
    assert cb.state == "open"


def test_open_circuit_fails_fast_without_calling_fn():
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=60)
    with pytest.raises(RuntimeError):
        cb.call(failing)
    assert cb.state == "open"

    calls = []
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: calls.append(1))
    assert calls == []  # fn was never actually invoked


def test_half_open_trial_success_closes_circuit():
    # A tight margin between cooldown_seconds and the sleep below is a
    # real source of flakiness under scheduler jitter (found by running
    # this suite dozens of times in a row, not by inspection) -- 0.01s
    # cooldown against a 0.2s sleep gives 20x headroom instead of 1.2x.
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
    with pytest.raises(RuntimeError):
        cb.call(failing)
    time.sleep(0.2)
    assert cb.call(succeeding) == "ok"
    assert cb.state == "closed"


def test_half_open_trial_failure_reopens_circuit():
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
    with pytest.raises(RuntimeError):
        cb.call(failing)
    time.sleep(0.2)
    with pytest.raises(RuntimeError):
        cb.call(failing)
    assert cb.state == "open"
