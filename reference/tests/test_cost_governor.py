import pytest

from sre_agent.cost_governor import BudgetExceeded, BudgetStore, call_with_budget, check_and_reserve_budget


def test_reserve_succeeds_within_budget():
    store = BudgetStore(daily_limit_by_caller={"tenant-a": 10.0})
    assert check_and_reserve_budget(store, "tenant-a", 4.0) is True
    assert store.remaining("tenant-a") == 6.0


def test_reserve_fails_over_budget():
    store = BudgetStore(daily_limit_by_caller={"tenant-a": 10.0})
    check_and_reserve_budget(store, "tenant-a", 9.0)
    assert check_and_reserve_budget(store, "tenant-a", 2.0) is False
    assert store.remaining("tenant-a") == 1.0  # the failed attempt did not spend anything


def test_one_tenant_exhausting_budget_does_not_affect_another():
    store = BudgetStore(daily_limit_by_caller={"tenant-a": 5.0, "tenant-b": 5.0})
    check_and_reserve_budget(store, "tenant-a", 5.0)
    assert check_and_reserve_budget(store, "tenant-a", 1.0) is False
    assert check_and_reserve_budget(store, "tenant-b", 5.0) is True


def test_call_with_budget_raises_when_exceeded():
    store = BudgetStore(daily_limit_by_caller={"tenant-a": 1.0})
    with pytest.raises(BudgetExceeded):
        call_with_budget(store, "tenant-a", 2.0, lambda: "should not run")


def test_call_with_budget_runs_fn_and_reserves_when_within_budget():
    store = BudgetStore(daily_limit_by_caller={"tenant-a": 5.0})
    result = call_with_budget(store, "tenant-a", 2.0, lambda: "ran")
    assert result == "ran"
    assert store.remaining("tenant-a") == 3.0
