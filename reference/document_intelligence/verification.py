"""Verification Gate (Chapter 23).

A check that runs after a step produces a result and before that result
is treated as fact, using a method genuinely independent of however the
result was produced -- here, a plain substring check against the source
document, not another model call.
"""

from __future__ import annotations

import re

from .schema import DocumentState


def _normalize_whitespace(text: str) -> str:
    """Collapse whitespace and strip ASCII-art formatting noise before
    comparing. Covers two real cases an exact substring check would
    otherwise reject as fabricated even though the model quoted the
    source correctly:

    1. A source document wraps a sentence across a line break, so the
       raw text has a newline where the model's quote (correctly) has
       a single space instead.
    2. A section heading is underlined with a run of dashes on its own
       line, common in real legal filings. Flattened without stripping
       it, that run of dashes lands as a stray token in the middle of
       a sentence the model quoted correctly."""
    text = re.sub(r"[-_=]{3,}", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def verify_extraction(document: str, field: str, value: str) -> bool:
    if not value:
        return False
    return _normalize_whitespace(value) in _normalize_whitespace(document)


def verify_document_state(document: str, state: DocumentState) -> dict:
    """Verifies every extracted fact against the source document.
    Returns which specific facts passed and which didn't, rather than a
    single pass/fail for the whole document -- a document with one bad
    field shouldn't have every other correctly-extracted field discarded
    along with it."""
    results = {"parties": [], "obligations": [], "clauses": []}

    for party in state.parties:
        results["parties"].append(
            {
                "party": party,
                "verified": verify_extraction(document, "name", party.name),
            }
        )
    for obligation in state.obligations:
        results["obligations"].append(
            {
                "obligation": obligation,
                "verified": verify_extraction(
                    document, "source_clause", obligation.source_clause
                ),
            }
        )
    for clause in state.clauses:
        results["clauses"].append(
            {
                "clause": clause,
                "verified": verify_extraction(document, "text", clause.text),
            }
        )
    return results


def all_verified(results: dict) -> bool:
    return all(item["verified"] for group in results.values() for item in group)
