"""True end-to-end live smoke test: the full assembled handle_incident
orchestrator, with a real live model (Gemini) actually making the
diagnosis call, not FakeModel.

Every other test either (a) exercises the orchestrator with FakeModel, or
(b) exercises a live model in isolation. Neither proves the whole real
system works together with a live model actually in the loop. This does.

Usage:
    export GEMINI_API_KEY=$(cat ../.env)
    python scripts/smoke_test_end_to_end.py
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
    registry.register("checkout", replicas=3, healthy=False)  # a real incident to diagnose

    deps = Dependencies(
        registry=registry,
        idempotency_store={},
        ledger=Ledger(),
        leases=LeaseStore(),
        tasks=TaskStore(),
        budget=BudgetStore(daily_limit_by_caller={"eng-1": 10.0}),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=60),
        primary_model=GeminiModel(),  # real, via the google-genai SDK
        fallback_model=OpenAICompatibleModel(  # also real, via the openai SDK -> Gemini's compatible endpoint
            model="gemini-3.6-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=os.environ["GEMINI_API_KEY"],
        ),
    )
    actor = Actor("eng-1", "on_call")

    result = handle_incident(deps, actor, "checkout", task_id="e2e-demo-1")

    print("=== Result ===")
    print(result)
    print("\n=== Full ledger trace for this task ===")
    for entry in deps.ledger.for_task("e2e-demo-1"):
        print(f"{entry.timestamp}  {entry.event_type:<22}  {entry.details}")

    assert result["status"] == "executed"
    assert registry.get("checkout")["restart_count"] == 1
    diagnosis = [e for e in deps.ledger.for_task("e2e-demo-1") if e.event_type == "diagnosis"][0]
    assert diagnosis.details["source"] == "model"  # confirms the real model actually answered
    print("\nOK: full orchestrator ran end to end with a real, live model making the diagnosis call.")


if __name__ == "__main__":
    main()
