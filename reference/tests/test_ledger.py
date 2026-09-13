from sre_agent.ledger import Ledger


def test_write_and_query_by_task_id_preserves_order():
    ledger = Ledger()
    ledger.write("task-1", "tool_call", {"fields": {"a": 1}})
    ledger.write("task-1", "verification_gate", {"passed": True})
    ledger.write("task-2", "tool_call", {"unrelated": True})

    entries = ledger.for_task("task-1")
    assert len(entries) == 2
    assert entries[0].event_type == "tool_call"
    assert entries[1].event_type == "verification_gate"
    assert entries[1].details == {"passed": True}


def test_unknown_task_id_returns_empty_list():
    ledger = Ledger()
    assert ledger.for_task("never-seen") == []
