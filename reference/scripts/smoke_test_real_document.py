"""Live smoke test against a REAL document, not a hand-written sample:
a genuine services agreement pulled from SEC EDGAR's public filing
archive (Fleurs De Vie, Inc. / Loev Corporate Filings, Inc., filed
2005-2006), with the real, messy formatting SEC full-text filings
actually have -- irregular double-spacing, underline artifacts, page
break markers. This is a harder, more realistic test than a clean
hand-written contract: if verify_extraction's whitespace normalization
only worked around one specific bug in one hand-crafted example, this
is where that would show.

The document was fetched once with:
    curl -A "<contact info>" https://www.sec.gov/Archives/edgar/data/1341780/000133227706000111/ex10-2.txt
and is a matter of public record (a filing under SEC full-text search).

Usage:
    export GEMINI_API_KEY=$(cat ../.env)
    python scripts/smoke_test_real_document.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_core.models import GeminiModel  # noqa: E402
from document_intelligence.evidence import answer_with_evidence  # noqa: E402
from document_intelligence.orchestrator import process_document  # noqa: E402
from document_intelligence.risk import DocumentMetadata  # noqa: E402

DOCUMENT = (Path(__file__).parent / "real_contract_clean.txt").read_text(encoding="utf-8")


def main() -> None:
    model = GeminiModel()

    print(f"Document length: {len(DOCUMENT)} characters (real SEC filing, not a hand-written sample)\n")
    print("=== Running all three specialists against a real model, on a real document ===")
    result = process_document(model, DOCUMENT, DocumentMetadata())

    print(f"\nParties found: {[(p.name, p.role) for p in result['state'].parties]}")
    print(f"Obligations found: {len(result['state'].obligations)}")
    print(f"Clauses found: {len(result['state'].clauses)}")
    print(f"\nAll facts verified against source text: {result['verified']}")
    print(f"Risk tier: {result['risk_tier']}")

    unverified_count = 0
    for group_name, items in result["verification"].items():
        for item in items:
            if not item["verified"]:
                unverified_count += 1
                print(f"  UNVERIFIED in {group_name}: {item}")

    print("\n=== Evidence-first question answering, real model, real document ===")
    for question in [
        "What is the term of this agreement?",
        "What compensation does Filings receive?",
        "What state's law governs this agreement?",
    ]:
        answer = answer_with_evidence(model, question, DOCUMENT)
        print(f"\nQ: {question}")
        print(f"Quote:  {answer.get('quote')!r}")
        print(f"Answer: {answer.get('answer')!r}")

    print(f"\n{'=' * 60}")
    if unverified_count == 0:
        print("OK: every fact extracted from a real, messily-formatted public filing verified cleanly.")
    else:
        print(f"NOTE: {unverified_count} fact(s) did not verify -- see details above.")


if __name__ == "__main__":
    main()
