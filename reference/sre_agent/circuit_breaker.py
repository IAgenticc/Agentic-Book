"""Agent Circuit Breaker (Chapter 27).

Tracks aggregate failures against one specific dependency and stops
sending new attempts once it looks broken, instead of every task
discovering the same break independently.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

T = TypeVar("T")


class CircuitOpenError(Exception):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int
    cooldown_seconds: float
    state: str = field(default="closed", init=False)
    failure_count: int = field(default=0, init=False)
    opened_at: float | None = field(default=None, init=False)

    def call(self, fn: Callable[[], T]) -> T:
        if self.state == "open":
            if self.opened_at is not None and time.monotonic() - self.opened_at < self.cooldown_seconds:
                raise CircuitOpenError("circuit is open")
            self.state = "half_open"

        try:
            result = fn()
        except Exception:
            self.failure_count += 1
            if self.state == "half_open" or self.failure_count >= self.failure_threshold:
                self.state = "open"
                self.opened_at = time.monotonic()
            raise
        else:
            self.state = "closed"
            self.failure_count = 0
            return result
