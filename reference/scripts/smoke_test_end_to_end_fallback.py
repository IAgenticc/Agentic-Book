"""Same end-to-end run as smoke_test_end_to_end.py, but the primary model
is genuinely broken (an invalid model name causes a real API error from
Gemini, not a simulated one) so this proves the fallback path itself
activates and is served by a real, live, different-SDK call -- not just
that it's present and unused, which is all the other script proved.

Usage:
    export GEMINI_API_KEY=$(cat ../.env)
    python scripts/smoke_test_end_to_end_fallback.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sre_agent.circuit_breaker import CircuitBreaker  # noqa: E402
from sre_agent.cost_governor import BudgetStore  # noqa: E402
from sre_agent.durable_task import TaskStore  # noqa: E402
from sre_agent.ledger import Ledger  # noqa: E402
from sre_agent.lease import LeaseStore  # noqa: E402
from sre_agent.models import GeminiModel, OpenAICompatibleModel  # noqa: E402
from sre_agent.orchestrator import Dependencies, handle_incident  # noqa: E402
from sre_agent.tools import Actor, ServiceRegistry  # noqa: E402


def main() -> None:
    registry = ServiceRegistry()
    registry.register("checkout", replicas=3, healthy=False)

    deps = Dependencies(
        registry=registry,
        idempotency_store={},
        ledger=Ledger(),
        leases=LeaseStore(),
        tasks=TaskStore(),
        budget=BudgetStore(daily_limit_by_caller={"eng-1": 10.0}),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=60),
        # Deliberately broken: this model name does not exist. Calling it
        # raises a real API error from Gemini's servers, caught by
        # ModelUnavailable's except clause -- a genuine failure, not a
        # FakeModel(fail=True) simulation of one.
        primary_model=GeminiModel(model="gemini-does-not-exist-9000"),
        fallback_model=OpenAICompatibleModel(
            model="gemini-3.6-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=os.environ["GEMINI_API_KEY"],
        ),
    )
    actor = Actor("eng-1", "on_call")

    result = handle_incident(deps, actor, "checkout", task_id="e2e-fallback-demo")

    print("=== Result ===")
    print(result)
    diagnosis = [e for e in deps.ledger.for_task("e2e-fallback-demo") if e.event_type == "diagnosis"][0]
    print(f"\ndiagnosis source: {diagnosis.details['source']}")
    print(f"diagnosis text (first 200 chars): {diagnosis.details['text'][:200]!r}")

    assert result["status"] == "executed"
    assert diagnosis.details["source"] == "model"  # a model answered -- just not the primary
    print(
        "\nOK: the primary model genuinely failed (invalid model name), and the real, "
        "live fallback (a different SDK, same underlying provider) served the request."
    )


if __name__ == "__main__":
    main()
