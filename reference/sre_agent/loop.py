"""Bounded Agent Loop (Chapter 4) and the Deterministic Shell (Chapter 5).

The model reasons; a plain, testable stop condition in code decides when
the loop is actually done, and a fixed step cap guarantees it ends
regardless of what the model says about its own progress.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .models import Model


@dataclass
class LoopResult:
    status: str  # "done" or "max_steps_reached"
    steps: int
    transcript: list[str] = field(default_factory=list)


def bounded_loop(
    model: Model,
    initial_prompt: str,
    is_done: Callable[[str], bool],
    max_steps: int = 6,
) -> LoopResult:
    prompt = initial_prompt
    transcript: list[str] = []
    for step in range(max_steps):
        response = model.generate(prompt)
        transcript.append(response)
        if is_done(response):
            return LoopResult(status="done", steps=step + 1, transcript=transcript)
        prompt = response
    return LoopResult(status="max_steps_reached", steps=max_steps, transcript=transcript)
