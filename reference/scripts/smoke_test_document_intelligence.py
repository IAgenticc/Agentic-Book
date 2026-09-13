"""True end-to-end live smoke test for the Document Intelligence Agent:
a real contract, a real live model (Gemini) actually running all three
specialists, real verification against the source text, and a real
evidence-first question answered afterward.

Usage:
    export GEMINI_API_KEY=$(cat ../.env)
    python scripts/smoke_test_document_intelligence.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from document_intelligence.evidence import answer_with_evidence  # noqa: E402
from document_intelligence.orchestrator import process_document  # noqa: E402
from document_intelligence.risk import DocumentMetadata  # noqa: E402
from document_intelligence.verification import verify_extraction  # noqa: E402
from agent_core.models import GeminiModel  # noqa: E402

CONTRACT = """
SERVICES AGREEMENT

This Services Agreement ("Agreement") is entered into between Northwind
Traders LLC ("Client") and Contoso Consulting Inc ("Consultant").

1. Services. Consultant shall provide software consulting services to
Client as described in Exhibit A.

2. Payment. Client shall pay Consultant $15,000 within 15 days of
receiving an invoice.

3. Term and Termination. This Agreement remains in effect for one year
from the effective date. Either party may terminate this Agreement with
45 days written notice.

4. Confidentiality. Consultant shall not disclose Client's confidential
information to any third party.
"""


def main() -> None:
    model = GeminiModel()

    print("=== Running all three specialists against a real model ===")
    result = process_document(model, CONTRACT, DocumentMetadata(contains_pii=False))

    print(f"\nParties found: {[(p.name, p.role) for p in result['state'].parties]}")
    print(f"Obligations found: {len(result['state'].obligations)}")
    print(f"Clauses found: {len(result['state'].clauses)}")
    print(f"\nAll facts verified against source text: {result['verified']}")
    print(f"Risk tier: {result['risk_tier']}")

    for group_name, items in result["verification"].items():
        for item in items:
            if not item["verified"]:
                print(f"  UNVERIFIED in {group_name}: {item}")

    print("\n=== Evidence-first question answering, real model ===")
    answer = answer_with_evidence(model, "What is the termination notice period?", CONTRACT)
    print(f"Quote:  {answer.get('quote')!r}")
    print(f"Answer: {answer.get('answer')!r}")

    assert result["verified"], "expected every real specialist output to verify against the real contract"
    assert answer["quote"] is not None and verify_extraction(CONTRACT, "quote", answer["quote"])
    assert "45" in answer["answer"]
    print("\nOK: full Document Intelligence Agent ran end to end with a real, live model.")


if __name__ == "__main__":
    main()
