from datetime import datetime, timedelta, timezone

from sre_agent.approval import propose_action, resolve
from sre_agent.ledger import Ledger


def test_approved_proposal_executes_and_logs():
    ledger = Ledger()
    proposal = propose_action("checkout", reasoning="unhealthy", blast_radius="one service")
    result = resolve(proposal, "approved", execute=lambda a: {"ran": a}, ledger=ledger, task_id="t1")
    assert result == {"status": "executed", "ran": True, "result": {"ran": "checkout"}}
    events = [e.event_type for e in ledger.for_task("t1")]
    assert "proposal_approved" in events


def test_rejected_proposal_never_executes_but_still_logs():
    ledger = Ledger()
    executed = []
    proposal = propose_action("checkout", reasoning="unhealthy", blast_radius="one service")
    result = resolve(proposal, "rejected", execute=lambda a: executed.append(a), ledger=ledger, task_id="t1")
    assert result == {"status": "discarded", "ran": False}
    assert executed == []
    events = [e.event_type for e in ledger.for_task("t1")]
    assert "proposal_rejected" in events


def test_expired_proposal_never_executes():
    ledger = Ledger()
    executed = []
    proposal = propose_action("checkout", reasoning="unhealthy", blast_radius="one service", ttl_minutes=0)
    proposal.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)  # force expiry
    result = resolve(proposal, "approved", execute=lambda a: executed.append(a), ledger=ledger, task_id="t1")
    assert result["status"] == "expired"
    assert executed == []
