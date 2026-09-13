"""Golden Set Regression (Chapter 28).

A fixed set of representative cases run in full before shipping any
change, checked specifically for regressions -- cases that used to pass
and now don't -- not just whether new results look acceptable overall.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class GoldenCase:
    name: str
    document: str
    question: str
    expected_answer_contains: str


@dataclass
class Result:
    name: str
    passed: bool
    actual: dict


def run_golden_set(cases: list[GoldenCase], answer_fn: Callable[[str, str], dict]) -> list[Result]:
    results = []
    for case in cases:
        actual = answer_fn(case.question, case.document)
        answer = (actual.get("answer") or "").lower()
        passed = case.expected_answer_contains.lower() in answer
        results.append(Result(name=case.name, passed=passed, actual=actual))
    return results


def check_for_regressions(before: list[Result], after: list[Result]) -> list[str]:
    by_name = {r.name: r for r in after}
    return [b.name for b in before if b.passed and not by_name[b.name].passed]
