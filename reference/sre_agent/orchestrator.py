"""The assembled SRE Agent: one incident-response flow wiring together
every pattern module in this package.

This is the concrete thing Chapter 41 walks through end to end:
  1. Audit Ledger (Ch 29)     - every step below writes here
  2. Resource Lease (Ch 34)   - only one task works a given service at once
  3. Circuit Breaker (Ch 27)  - guards the call to the status-check dependency
  4. Capability-Scoped Tools (Ch 16) - the actor's role decides what it can do
  5. Model Fallback (Ch 26) + Cost Governor (Ch 25) - the diagnosis call
  6. Proposal-Approval-Execution (Ch 18) - a human decides on the fix
  7. Durable Task Graph (Ch 22) + Idempotent Tool Action (Ch 20) - the fix itself
"""
from __future__ import annotations

from dataclasses import dataclass

from .approval import Proposal, propose_action, resolve
from .circuit_breaker import CircuitBreaker
from .cost_governor import BudgetStore, check_and_reserve_budget
from .durable_task import Step, TaskStore, resume
from .ledger import Ledger
from .lease import LeaseDenied, LeaseStore, with_lease
from .models import Model, call_with_fallback
from .tools import Actor, ServiceRegistry, get_service_status, restart_service, tools_for


@dataclass
class Dependencies:
    registry: ServiceRegistry
    idempotency_store: dict
    ledger: Ledger
    leases: LeaseStore
    tasks: TaskStore
    budget: BudgetStore
    breaker: CircuitBreaker
    primary_model: Model
    fallback_model: Model


def degraded_diagnosis(_prompt: str) -> dict:
    """No-model degraded mode (Chapter 26): a fixed, safe default used
    when both models are unavailable."""
    return {"text": "restart", "source": "degraded", "elapsed": 0.0}


def handle_incident(deps: Dependencies, actor: Actor, service: str, task_id: str) -> dict:
    deps.ledger.write(task_id, "incident_started", {"service": service, "actor": actor.id})

    def do_incident() -> dict:
        # Capability scoping (Ch 16): decide what this actor can even see.
        available = tools_for(actor)
        deps.ledger.write(task_id, "tools_scoped", {"available": available})

        # Circuit breaker (Ch 27) around the status-check dependency.
        status = deps.breaker.call(lambda: get_service_status(deps.registry, service))
        deps.ledger.write(task_id, "status_checked", status)

        if status["healthy"]:
            deps.ledger.write(task_id, "no_action_needed", {})
            return {"status": "healthy", "ran": False}

        # Cost-governed, fallback-protected diagnosis call.
        if not check_and_reserve_budget(deps.budget, actor.id, estimated_cost=0.02):
            deps.ledger.write(task_id, "budget_exceeded", {"actor": actor.id})
            return {"status": "budget_exceeded", "ran": False}

        diagnosis = call_with_fallback(
            prompt=f"Service {service} is unhealthy. Recommend an action.",
            primary=deps.primary_model,
            fallback=deps.fallback_model,
            degraded=degraded_diagnosis,
        )
        deps.ledger.write(task_id, "diagnosis", diagnosis)

        if "restart_service" not in available:
            deps.ledger.write(task_id, "escalated_no_capability", {"actor": actor.id})
            return {"status": "escalated", "ran": False, "reason": "actor cannot restart"}

        # Proposal-Approval-Execution (Ch 18).
        proposal = propose_action(
            action=service,
            reasoning=f"Status check found {service} unhealthy; diagnosis: {diagnosis['text']}",
            blast_radius=f"Restarts exactly one service: {service}",
        )
        deps.ledger.write(task_id, "proposal_created", {"action": proposal.action})

        def execute_restart(target_service: str) -> dict:
            # Durable Task Graph (Ch 22) wrapping the one idempotent step (Ch 20).
            plan = [
                Step(
                    name="restart",
                    execute=lambda: restart_service(
                        deps.registry, deps.idempotency_store, target_service, idempotency_key=task_id
                    ),
                )
            ]
            ran = resume(deps.tasks, task_id, plan)
            return {"ran_steps": ran}

        decision = "approved" if actor.role in ("on_call", "sre_lead") else "rejected"
        outcome = resolve(proposal, decision, execute_restart, deps.ledger, task_id)
        return outcome

    try:
        return with_lease(deps.leases, resource_id=service, holder_id=task_id, ttl_seconds=120, fn=do_incident)
    except LeaseDenied as exc:
        deps.ledger.write(task_id, "lease_denied", {"service": service, "reason": str(exc)})
        return {"status": "lease_denied", "ran": False}
