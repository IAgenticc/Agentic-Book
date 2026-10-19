"""The assembled Document Intelligence Agent: three specialists running
through a shared Blackboard (Chapter 35), their output independently
verified (Chapter 23), and the document risk-classified (Chapter 17).

Party identification and clause extraction run with no dependency on
each other -- genuinely in parallel, on real threads. Obligation
extraction has one real dependency (it needs the parties list) and
blocks on board.wait_for("parties") for exactly that, and nothing else,
which is the actual point of Chapter 35's pattern: no orchestrator
explicitly sequencing all three, just one specialist expressing the one
dependency it actually has.
"""

from __future__ import annotations

import threading

from .blackboard import Blackboard
from .risk import DocumentMetadata, classify_risk
from .specialists import clause_extraction, obligation_extraction, party_identification
from .verification import all_verified, verify_document_state


class SpecialistFailure(RuntimeError):
    """One or more specialists failed to complete. A thread's own exception
    never reaches the thread that joined it, so each specialist is run
    through this wrapper and its exception, if any, collected and raised
    here instead of disappearing silently."""

    def __init__(self, errors: dict[str, BaseException]):
        super().__init__(", ".join(f"{name}: {err}" for name, err in errors.items()))
        self.errors = errors


def process_document(model, document: str, metadata: DocumentMetadata) -> dict:
    board = Blackboard()
    errors: dict[str, BaseException] = {}

    def run(name, specialist):
        try:
            specialist(model, document, board)
        except Exception as exc:  # noqa: BLE001 -- re-raised as SpecialistFailure below
            errors[name] = exc

    threads = [
        threading.Thread(target=run, args=("parties", party_identification)),
        threading.Thread(target=run, args=("obligations", obligation_extraction)),
        threading.Thread(target=run, args=("clauses", clause_extraction)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        raise SpecialistFailure(errors)

    state = board.snapshot()
    verification = verify_document_state(document, state)
    risk_tier = classify_risk(metadata)

    return {
        "state": state,
        "verification": verification,
        "verified": all_verified(verification),
        "risk_tier": risk_tier,
    }
