"""Three specialists coordinating through the Blackboard (Chapter 35),
each producing Typed State (Chapter 36). None of them know about each
other -- only about the board.
"""
from __future__ import annotations

import json
import re

from agent_core.models import Model

from .blackboard import Blackboard
from .schema import Clause, Obligation, PartyRecord

PARTY_PROMPT = """Identify every named party in this contract and their role
(e.g. buyer, seller, contractor). Respond with ONLY a JSON array, no
other text, in this exact shape:
[{{"name": "...", "role": "..."}}]

Document:
{document}
"""

OBLIGATION_PROMPT = """Given these parties: {parties}

Identify each party's obligations under this contract. Respond with ONLY
a JSON array, no other text, in this exact shape:
[{{"party": "...", "description": "...", "source_clause": "..."}}]

Document:
{document}
"""

CLAUSE_PROMPT = """Identify the distinct clauses in this contract, each with
a short heading and its exact text. Respond with ONLY a JSON array, no
other text, in this exact shape:
[{{"heading": "...", "text": "..."}}]

Document:
{document}
"""


def _extract_json(text: str) -> str:
    """Models often wrap JSON output in a markdown code fence even when
    told not to. Strip it before parsing rather than fail on it."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def party_identification(model: Model, document: str, board: Blackboard) -> None:
    response = model.generate(PARTY_PROMPT.format(document=document))
    raw = json.loads(_extract_json(response))
    parties = [PartyRecord(**p) for p in raw]
    board.write("parties", parties)


def obligation_extraction(model: Model, document: str, board: Blackboard) -> None:
    parties = board.wait_for("parties")
    prompt = OBLIGATION_PROMPT.format(parties=[p.name for p in parties], document=document)
    response = model.generate(prompt)
    raw = json.loads(_extract_json(response))
    obligations = [Obligation(**o) for o in raw]
    board.write("obligations", obligations)


def clause_extraction(model: Model, document: str, board: Blackboard) -> None:
    response = model.generate(CLAUSE_PROMPT.format(document=document))
    raw = json.loads(_extract_json(response))
    clauses = [Clause(**c) for c in raw]
    board.write("clauses", clauses)
