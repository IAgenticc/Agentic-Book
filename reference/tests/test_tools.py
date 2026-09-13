import pytest

from sre_agent.tools import Actor, ServiceRegistry, UnknownServiceError, get_service_status, restart_service, scale_to, tools_for


def make_registry():
    reg = ServiceRegistry()
    reg.register("checkout", replicas=3, healthy=False)
    return reg


def test_get_service_status_is_read_only_and_accurate():
    reg = make_registry()
    status = get_service_status(reg, "checkout")
    assert status["healthy"] is False
    assert status["replicas"] == 3


def test_restart_service_is_idempotent_on_same_key():
    reg = make_registry()
    idem = {}
    first = restart_service(reg, idem, "checkout", idempotency_key="task-1")
    second = restart_service(reg, idem, "checkout", idempotency_key="task-1")
    assert first == second
    assert reg.get("checkout")["restart_count"] == 1  # not 2


def test_restart_service_different_keys_do_restart_twice():
    reg = make_registry()
    idem = {}
    restart_service(reg, idem, "checkout", idempotency_key="task-1")
    restart_service(reg, idem, "checkout", idempotency_key="task-2")
    assert reg.get("checkout")["restart_count"] == 2


def test_restart_service_rejects_unknown_service():
    reg = make_registry()
    with pytest.raises(UnknownServiceError):
        restart_service(reg, {}, "does-not-exist", idempotency_key="task-1")


def test_scale_to_is_idempotent_target_state():
    reg = make_registry()
    first = scale_to(reg, "checkout", target_replicas=5)
    second = scale_to(reg, "checkout", target_replicas=5)
    assert first["changed"] is True
    assert second["changed"] is False
    assert reg.get("checkout")["replicas"] == 5


def test_tools_for_scopes_by_role():
    assert tools_for(Actor("dash", "read_only")) == ["get_service_status"]
    assert "restart_service" in tools_for(Actor("eng", "on_call"))
    assert "scale_to" not in tools_for(Actor("eng", "on_call"))
    assert "scale_to" in tools_for(Actor("lead", "sre_lead"))
