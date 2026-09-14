"""Real HTTP-level tests for sre_agent/api.py, using FastAPI's TestClient
(a genuine ASGI request/response cycle, not a mock of the transport
layer). Appendix C walks through each of these scenarios by hand with
curl; these are the same scenarios kept as permanent regression tests.
"""
from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from sre_agent.api import app
from sre_agent.models import FakeModel


def test_restart_flow_for_unhealthy_service():
    with TestClient(app) as client:
        resp = client.post(
            "/incidents",
            json={"service": "checkout", "actor_id": "on-call-engineer", "actor_role": "on_call"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "executed"
        assert body["result"]["ran_steps"] == ["restart"]


def test_healthy_service_needs_no_action():
    with TestClient(app) as client:
        resp = client.post(
            "/incidents",
            json={"service": "payments", "actor_id": "on-call-engineer", "actor_role": "on_call"},
        )
        assert resp.json()["status"] == "healthy"


def test_read_only_actor_is_escalated_not_restarted():
    with TestClient(app) as client:
        resp = client.post(
            "/incidents",
            json={"service": "checkout", "actor_id": "auditor", "actor_role": "read_only"},
        )
        assert resp.json()["status"] == "escalated"


def test_repeat_task_id_does_not_restart_twice():
    with TestClient(app) as client:
        payload = {
            "service": "checkout",
            "actor_id": "on-call-engineer",
            "actor_role": "on_call",
            "task_id": "fix-1",
        }
        first = client.post("/incidents", json=payload).json()
        assert first["result"]["ran_steps"] == ["restart"]

        # A caller retrying the same request (a timeout, a duplicate
        # delivery) wouldn't know the fix already landed -- simulate that
        # by putting the service back in the "still looks unhealthy" state
        # a monitoring check that hasn't caught up yet would report.
        app.state.deps.registry.services["checkout"]["healthy"] = False
        second = client.post("/incidents", json=payload).json()
        # Same task_id: the durable task graph sees "restart" already
        # completed and skips it, Chapter 22's actual point, instead of
        # restarting a second time just because the caller asked again.
        assert second["result"]["ran_steps"] == []


def test_concurrent_requests_for_same_service_one_is_denied():
    with TestClient(app) as client:
        # A deterministic version of the fifty-thread stress test Chapter 34
        # and Chapter 41 describe: make the diagnosis call slow enough that
        # a second request is guaranteed to race the first one for the same
        # service's lease, instead of hoping enough threads eventually
        # collide.
        app.state.deps.primary_model = FakeModel(
            responder=lambda p: (time.sleep(0.3), "restart")[1]
        )

        results: list[dict] = []

        def fire(task_id: str) -> None:
            resp = client.post(
                "/incidents",
                json={
                    "service": "checkout",
                    "actor_id": "on-call-engineer",
                    "actor_role": "on_call",
                    "task_id": task_id,
                },
            )
            results.append(resp.json())

        first_thread = threading.Thread(target=fire, args=("race-1",))
        second_thread = threading.Thread(target=fire, args=("race-2",))
        first_thread.start()
        time.sleep(0.05)  # let the first request actually acquire the lease
        second_thread.start()
        first_thread.join()
        second_thread.join()

        statuses = sorted(r["status"] for r in results)
        assert statuses == ["executed", "lease_denied"]


def test_unknown_service_is_404():
    with TestClient(app) as client:
        resp = client.post(
            "/incidents",
            json={"service": "does-not-exist", "actor_id": "on-call-engineer", "actor_role": "on_call"},
        )
        assert resp.status_code == 404


def test_circuit_opens_after_repeated_unknown_service_calls():
    with TestClient(app) as client:
        for i in range(3):
            client.post(
                "/incidents",
                json={
                    "service": "does-not-exist",
                    "actor_id": "on-call-engineer",
                    "actor_role": "on_call",
                    "task_id": f"probe-{i}",
                },
            )
        resp = client.post(
            "/incidents",
            json={
                "service": "does-not-exist",
                "actor_id": "on-call-engineer",
                "actor_role": "on_call",
                "task_id": "probe-final",
            },
        )
        assert resp.status_code == 503


def test_budget_exhausted_actor_is_denied():
    with TestClient(app) as client:
        resp = client.post(
            "/incidents",
            json={"service": "checkout", "actor_id": "broke-actor", "actor_role": "on_call"},
        )
        assert resp.json()["status"] == "budget_exceeded"


def test_malformed_request_is_422():
    with TestClient(app) as client:
        resp = client.post("/incidents", json={"service": "checkout"})
        assert resp.status_code == 422


def test_ledger_reflects_the_incident():
    with TestClient(app) as client:
        create = client.post(
            "/incidents",
            json={
                "service": "checkout",
                "actor_id": "on-call-engineer",
                "actor_role": "on_call",
                "task_id": "ledger-check",
            },
        ).json()
        ledger = client.get(f"/incidents/{create['task_id']}/ledger").json()
        event_types = [entry["event_type"] for entry in ledger]
        assert "incident_started" in event_types
        assert "proposal_approved" in event_types


def test_unknown_task_id_ledger_is_404():
    with TestClient(app) as client:
        resp = client.get("/incidents/never-happened/ledger")
        assert resp.status_code == 404
