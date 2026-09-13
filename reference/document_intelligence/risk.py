"""Risk-Tiered Release Gate (Chapter 17).

A plain, deterministic function -- testable with real example documents
the same way any other code is tested, unlike a policy document nobody
checks.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocumentMetadata:
    contains_pii: bool = False
    crosses_data_boundary: bool = False
    legal_hold: bool = False


def classify_risk(metadata: DocumentMetadata) -> str:
    if metadata.crosses_data_boundary or metadata.legal_hold:
        return "high"
    if metadata.contains_pii:
        return "medium"
    return "low"
