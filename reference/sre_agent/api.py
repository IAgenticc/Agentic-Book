"""A minimal FastAPI wrapper around handle_incident (Chapter 41's
orchestrator), exposing the same seven patterns through a real HTTP
interface instead of a direct Python call.

This is genuinely runnable: `uvicorn sre_agent.api:app --reload` starts a
real server, and every request Appendix C's walkthrough shows is a real
request against it, not a transcript. See tests/test_api.py for the same
scenarios kept as permanent regression tests.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .cost_governor import BudgetStore
from .durable_task import TaskStore
from .ledger import Ledger
from .lease import LeaseStore
from .models import FakeModel
from .orchestrator import Dependencies, handle_incident
from .tools import Actor, ServiceRegistry, UnknownServiceError


def build_demo_dependencies() -> Dependencies:
    """Wires a real (if in-memory) instance of every pattern module,
    seeded so the failure walkthroughs in Appendix C are reachable
    without any extra setup:

    - "checkout" starts unhealthy, so restarting it is the first thing
      to try; "payments" starts healthy, showing the no-action path.
    - "on-call-engineer" and "auditor" both have real budget, so their
      different outcomes (executed vs. escalated) come from capability
      scoping, not from running out of money. "broke-actor" has none,
      isolating the budget gate on its own.
    """
    registry = ServiceRegistry()
    registry.register("checkout", healthy=False)
    registry.register("payments", healthy=True)

    budget = BudgetStore(
        daily_limit_by_caller={
            "on-call-engineer": 1.00,
            "auditor": 1.00,
            "broke-actor": 0.0,
        }
    )

    return Dependencies(
        registry=registry,
        idempotency_store={},
        ledger=Ledger(),
        leases=LeaseStore(),
        tasks=TaskStore(),
        budget=budget,
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0),
        primary_model=FakeModel(responder=lambda p: "Restart the service; it is failing health checks."),
        fallback_model=FakeModel(responder=lambda p: "Restart the service (fallback diagnosis)."),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Built fresh on every startup (including once per test's TestClient
    # context), so tests never leak state into each other despite `app`
    # itself being a module-level singleton.
    app.state.deps = build_demo_dependencies()
    yield


app = FastAPI(title="SRE Agent API", version="1.0.0", lifespan=lifespan)


class IncidentRequest(BaseModel):
    service: str
    actor_id: str
    actor_role: str = Field(pattern="^(read_only|on_call|sre_lead)$")
    # Optional client-supplied idempotency key, the same Chapter 20 concept
    # a real incident-response API needs: retry the same request safely by
    # sending the same task_id, instead of accidentally restarting twice.
    task_id: str | None = None


@app.post("/incidents")
def create_incident(req: IncidentRequest):
    actor = Actor(id=req.actor_id, role=req.actor_role)
    task_id = req.task_id or str(uuid.uuid4())
    try:
        result = handle_incident(app.state.deps, actor, req.service, task_id)
    except UnknownServiceError as exc:
        # A request for a service that was never registered isn't a
        # concurrency or capability problem -- it's bad input, and belongs
        # at this boundary, not inside the orchestrator itself.
        raise HTTPException(status_code=404, detail=f"unknown service: {exc}") from exc
    except CircuitOpenError as exc:
        # The breaker itself decided this dependency looks broken and is
        # refusing to even try. 503, not 500: the service is correctly
        # protecting itself, not failing unexpectedly.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"task_id": task_id, **result}


@app.get("/incidents/{task_id}/ledger")
def get_incident_ledger(task_id: str):
    entries = app.state.deps.ledger.for_task(task_id)
    if not entries:
        raise HTTPException(status_code=404, detail="no ledger entries for this task_id")
    return [asdict(e) for e in entries]
