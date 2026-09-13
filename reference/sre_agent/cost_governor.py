"""Cost Governor (Chapter 25).

Scopes a spend limit to the caller that can actually cause a runaway
(per-customer, per-task) rather than one undivided system-wide budget,
and checks remaining budget before an expensive call, not after.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(Exception):
    pass


@dataclass
class BudgetStore:
    daily_limit_by_caller: dict[str, float] = field(default_factory=dict)
    spent_by_caller: dict[str, float] = field(default_factory=dict)

    def remaining(self, caller_id: str) -> float:
        limit = self.daily_limit_by_caller.get(caller_id, 0.0)
        spent = self.spent_by_caller.get(caller_id, 0.0)
        return limit - spent

    def reserve(self, caller_id: str, amount: float) -> None:
        self.spent_by_caller[caller_id] = self.spent_by_caller.get(caller_id, 0.0) + amount


def check_and_reserve_budget(store: BudgetStore, caller_id: str, estimated_cost: float) -> bool:
    if estimated_cost > store.remaining(caller_id):
        return False
    store.reserve(caller_id, estimated_cost)
    return True


def call_with_budget(store: BudgetStore, caller_id: str, estimated_cost: float, fn):
    if not check_and_reserve_budget(store, caller_id, estimated_cost):
        raise BudgetExceeded(f"{caller_id} has insufficient remaining budget")
    return fn()
