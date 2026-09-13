"""The Blackboard Pattern (Chapter 35).

Specialists coordinate through a shared, structured piece of state
rather than through an orchestrator that explicitly decides who runs
when. Each specialist watches the board for what it needs, contributes
its own findings once it has enough to work with.
"""
from __future__ import annotations

import threading

from .schema import DocumentState


class Blackboard:
    def __init__(self):
        self._state = DocumentState()
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}

    def _event_for(self, field: str) -> threading.Event:
        with self._lock:
            if field not in self._events:
                self._events[field] = threading.Event()
            return self._events[field]

    def write(self, field: str, value) -> None:
        with self._lock:
            setattr(self._state, field, value)
        self._event_for(field).set()

    def read(self, field: str):
        with self._lock:
            return getattr(self._state, field)

    def wait_for(self, field: str, timeout: float = 10.0):
        """Block until `field` has been written, then return its value.
        A real wait condition, not a hopeful assumption about timing --
        see Chapter 35's warning about specialists that read a field
        before it's actually ready."""
        if not self._event_for(field).wait(timeout):
            raise TimeoutError(f"timed out waiting for board field {field!r}")
        return self.read(field)

    def snapshot(self) -> DocumentState:
        with self._lock:
            return self._state.model_copy(deep=True)
