"""Tools for the SRE Agent.

Combines several patterns: Capability-Scoped Tools and the
Blast-Radius Boundary (Chapter 16), and Idempotent Tool Action
(Chapter 20) for the one write-capable tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class UnknownServiceError(Exception):
    pass


@dataclass
class ServiceRegistry:
    """A tiny in-memory stand-in for whatever real infrastructure API
    these tools would call in production."""

    services: dict[str, dict] = field(default_factory=dict)

    def register(self, name: str, replicas: int = 3, healthy: bool = True) -> None:
        self.services[name] = {"replicas": replicas, "healthy": healthy, "restart_count": 0}

    def get(self, name: str) -> dict:
        if name not in self.services:
            raise UnknownServiceError(name)
        return self.services[name]


@dataclass
class Actor:
    id: str
    role: str  # "read_only", "on_call", "sre_lead"


def get_service_status(registry: ServiceRegistry, service: str) -> dict:
    """Read-only. Safe for every actor role."""
    return dict(registry.get(service))


def restart_service(registry: ServiceRegistry, idempotency_store: dict, service: str, idempotency_key: str) -> dict:
    """Idempotent Tool Action (Chapter 20): the same idempotency_key
    returns the cached result instead of restarting twice. Blast radius
    (Chapter 16) is bounded to exactly one named, known service."""
    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    entry = registry.get(service)  # raises UnknownServiceError for an unknown/wildcard target
    entry["restart_count"] += 1
    entry["healthy"] = True
    result = {"service": service, "restarted": True, "restart_count": entry["restart_count"]}
    idempotency_store[idempotency_key] = result
    return result


def scale_to(registry: ServiceRegistry, service: str, target_replicas: int) -> dict:
    """Target-state, naturally idempotent (Chapter 20): retrying a call
    that already reached target_replicas is a safe no-op."""
    entry = registry.get(service)
    if entry["replicas"] == target_replicas:
        return {"service": service, "replicas": target_replicas, "changed": False}
    entry["replicas"] = target_replicas
    return {"service": service, "replicas": target_replicas, "changed": True}


def tools_for(actor: Actor) -> list[str]:
    """Capability-Scoped Tools (Chapter 16): the tool list itself differs
    by caller, decided before the model ever gets a turn to reason about it."""
    available = ["get_service_status"]
    if actor.role in ("on_call", "sre_lead"):
        available.append("restart_service")
    if actor.role == "sre_lead":
        available.append("scale_to")
    return available
