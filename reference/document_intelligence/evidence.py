"""Evidence-Before-Fact (Chapter 30).

Requires the specific supporting text to be located and quoted before a
claim about it gets stated. Structures generation as quote-first,
conclude-second, then independently verifies the quote actually appears
in the source -- Chapter 23's Verification Gate again, applied to a
claim that comes with its own evidence attached.
"""
from __future__ import annotations

import re

from agent_core.models import Model

from .verification import verify_extraction

EVIDENCE_FIRST_PROMPT = """Find and quote the exact sentence in the document
that answers this question. Then state your answer based only on that
quote. If no sentence addresses the question, say so instead of
guessing. Respond in exactly this format:

Quote: <the exact quoted sentence, or "none">
Answer: <your answer based on the quote, or "not specified in this document">

Question: {question}

Document:
{document}
"""

_QUOTE_RE = re.compile(r"Quote:\s*(.*?)\s*(?:\n|$)")
_ANSWER_RE = re.compile(r"Answer:\s*(.*?)\s*$", re.DOTALL)


def parse_quote_and_answer(response: str) -> tuple[str | None, str]:
    quote_match = _QUOTE_RE.search(response)
    answer_match = _ANSWER_RE.search(response)
    quote = quote_match.group(1).strip().strip('"') if quote_match else None
    answer = answer_match.group(1).strip() if answer_match else response.strip()
    if quote and quote.lower() == "none":
        quote = None
    return quote, answer


def answer_with_evidence(model: Model, question: str, document: str) -> dict:
    response = model.generate(EVIDENCE_FIRST_PROMPT.format(question=question, document=document))
    quote, answer = parse_quote_and_answer(response)
    if quote and not verify_extraction(document, "quote", quote):
        return {"answer": None, "quote": quote, "reason": "quoted text not found in source"}
    return {"answer": answer, "quote": quote}
