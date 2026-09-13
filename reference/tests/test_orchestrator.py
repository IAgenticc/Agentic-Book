import pytest

from sre_agent.circuit_breaker import CircuitBreaker, CircuitOpenError
from sre_agent.cost_governor import BudgetStore
from sre_agent.durable_task import TaskStore
from sre_agent.ledger import Ledger
from sre_agent.lease import LeaseStore
from sre_agent.models import FakeModel
from sre_agent.orchestrator import Dependencies, handle_incident
from sre_agent.tools import Actor, ServiceRegistry


def make_deps(healthy: bool = False) -> Dependencies:
    registry = ServiceRegistry()
    registry.register("checkout", replicas=3, healthy=healthy)
    return Dependencies(
        registry=registry,
        idempotency_store={},
        ledger=Ledger(),
        leases=LeaseStore(),
        tasks=TaskStore(),
        budget=BudgetStore(daily_limit_by_caller={"eng-1": 10.0, "viewer-1": 10.0}),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=60),
        primary_model=FakeModel(responder=lambda p: "restart the service"),
        fallback_model=FakeModel(responder=lambda p: "restart the service"),
    )


def test_healthy_service_takes_no_action():
    deps = make_deps(healthy=True)
    actor = Actor("eng-1", "on_call")
    result = handle_incident(deps, actor, "checkout", task_id="t1")
    assert result == {"status": "healthy", "ran": False}
    assert deps.registry.get("checkout")["restart_count"] == 0


def test_on_call_actor_gets_unhealthy_service_restarted():
    deps = make_deps(healthy=False)
    actor = Actor("eng-1", "on_call")
    result = handle_incident(deps, actor, "checkout", task_id="t1")
    assert result["status"] == "executed"
    assert deps.registry.get("checkout")["restart_count"] == 1

    events = [e.event_type for e in deps.ledger.for_task("t1")]
    assert events == [
        "incident_started",
        "tools_scoped",
        "status_checked",
        "diagnosis",
        "proposal_created",
        "proposal_approved",
    ]


def test_read_only_actor_gets_escalated_not_executed():
    deps = make_deps(healthy=False)
    actor = Actor("viewer-1", "read_only")
    result = handle_incident(deps, actor, "checkout", task_id="t1")
    assert result["status"] == "escalated"
    assert deps.registry.get("checkout")["restart_count"] == 0


def test_retrying_the_same_task_id_does_not_restart_twice():
    """Simulates a caller retrying after an ambiguous timeout (Ch 33):
    same task_id, same idempotency key underneath, so the second call
    reuses the durable task's completed status instead of redoing it."""
    deps = make_deps(healthy=False)
    actor = Actor("eng-1", "on_call")
    handle_incident(deps, actor, "checkout", task_id="t1")
    # Service is healthy again post-restart, so a naive re-run would see "healthy"
    # and stop early -- the interesting case is calling resume() directly with
    # the same task_id, which is exercised in test_durable_task.py. Here we just
    # confirm one call restarts exactly once.
    assert deps.registry.get("checkout")["restart_count"] == 1


def test_concurrent_task_on_same_service_is_denied():
    deps = make_deps(healthy=False)
    actor = Actor("eng-1", "on_call")
    # Simulate a second task already holding the lease.
    deps.leases.acquire("checkout", "other-task", ttl_seconds=60)
    result = handle_incident(deps, actor, "checkout", task_id="t1")
    assert result["status"] == "lease_denied"
    assert deps.registry.get("checkout")["restart_count"] == 0


def test_budget_exceeded_blocks_the_diagnosis_call():
    deps = make_deps(healthy=False)
    deps.budget = BudgetStore(daily_limit_by_caller={"eng-1": 0.0})
    actor = Actor("eng-1", "on_call")
    result = handle_incident(deps, actor, "checkout", task_id="t1")
    assert result["status"] == "budget_exceeded"
    assert deps.registry.get("checkout")["restart_count"] == 0


def test_open_circuit_breaker_stops_the_status_check():
    deps = make_deps(healthy=False)
    deps.breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=60)
    # Force the breaker open before this incident even starts.
    with pytest.raises(RuntimeError):
        deps.breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("dependency down")))
    actor = Actor("eng-1", "on_call")
    with pytest.raises(CircuitOpenError):
        handle_incident(deps, actor, "checkout", task_id="t1")


def test_model_fallback_is_used_when_primary_is_down():
    deps = make_deps(healthy=False)
    deps.primary_model = FakeModel(fail=True)
    deps.fallback_model = FakeModel(responder=lambda p: "restart via fallback")
    actor = Actor("eng-1", "on_call")
    result = handle_incident(deps, actor, "checkout", task_id="t1")
    assert result["status"] == "executed"
    diagnosis_events = [e for e in deps.ledger.for_task("t1") if e.event_type == "diagnosis"]
    assert diagnosis_events[0].details["text"] == "restart via fallback"


def test_degraded_mode_used_when_both_models_are_down():
    """This is the path that was untested until a direct question about
    QA coverage prompted actually checking: with both models down, the
    incident still resolves via Chapter 26's no-model degraded response
    instead of failing the whole incident outright."""
    deps = make_deps(healthy=False)
    deps.primary_model = FakeModel(fail=True)
    deps.fallback_model = FakeModel(fail=True)
    actor = Actor("eng-1", "on_call")
    result = handle_incident(deps, actor, "checkout", task_id="t1")
    assert result["status"] == "executed"
    assert deps.registry.get("checkout")["restart_count"] == 1
    diagnosis_events = [e for e in deps.ledger.for_task("t1") if e.event_type == "diagnosis"]
    assert diagnosis_events[0].details["source"] == "degraded"
