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


def process_document(model, document: str, metadata: DocumentMetadata) -> dict:
    board = Blackboard()

    threads = [
        threading.Thread(target=party_identification, args=(model, document, board)),
        threading.Thread(target=obligation_extraction, args=(model, document, board)),
        threading.Thread(target=clause_extraction, args=(model, document, board)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    state = board.snapshot()
    verification = verify_document_state(document, state)
    risk_tier = classify_risk(metadata)

    return {
        "state": state,
        "verification": verification,
        "verified": all_verified(verification),
        "risk_tier": risk_tier,
    }
