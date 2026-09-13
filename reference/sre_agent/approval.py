"""Proposal-Approval-Execution (Chapter 18).

An agent that reaches a high-risk action builds a proposal carrying the
action, its reasoning, and its blast radius. Only an explicit approval
lets it run, and a stale, unresolved proposal expires rather than
executing on old reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


@dataclass
class Proposal:
    action: str
    reasoning: str
    blast_radius: str
    expires_at: datetime


def propose_action(action: str, reasoning: str, blast_radius: str, ttl_minutes: int = 15) -> Proposal:
    return Proposal(
        action=action,
        reasoning=reasoning,
        blast_radius=blast_radius,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )


def resolve(proposal: Proposal, decision: str, execute: Callable[[str], dict], ledger, task_id: str) -> dict:
    """decision is "approved" or "rejected". Every path writes to the ledger,
    since a rejection is worth recording just as much as an approval."""
    if datetime.now(timezone.utc) > proposal.expires_at:
        ledger.write(task_id, "proposal_expired", {"action": proposal.action})
        return {"status": "expired", "ran": False}

    if decision == "approved":
        result = execute(proposal.action)
        ledger.write(task_id, "proposal_approved", {"action": proposal.action, "result": result})
        return {"status": "executed", "ran": True, "result": result}

    ledger.write(task_id, "proposal_rejected", {"action": proposal.action})
    return {"status": "discarded", "ran": False}
