import threading
import time

import pytest

from document_intelligence.blackboard import Blackboard
from document_intelligence.schema import PartyRecord


def test_write_then_read_returns_the_value():
    board = Blackboard()
    parties = [PartyRecord(name="Acme Corp", role="buyer")]
    board.write("parties", parties)
    assert board.read("parties") == parties


def test_wait_for_blocks_until_written_then_returns_the_value():
    board = Blackboard()
    result = {}

    def waiter():
        result["parties"] = board.wait_for("parties", timeout=2)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.05)  # give the waiter a real chance to actually be blocked
    assert "parties" not in result  # confirms it was genuinely waiting, not racing ahead
    parties = [PartyRecord(name="Acme Corp", role="buyer")]
    board.write("parties", parties)
    t.join(timeout=2)
    assert result["parties"] == parties


def test_wait_for_times_out_if_never_written():
    board = Blackboard()
    with pytest.raises(TimeoutError):
        board.wait_for("parties", timeout=0.1)


def test_snapshot_is_a_copy_not_a_live_reference():
    board = Blackboard()
    board.write("parties", [PartyRecord(name="Acme Corp", role="buyer")])
    snap = board.snapshot()
    board.write("parties", [PartyRecord(name="Widget Inc", role="seller")])
    assert snap.parties[0].name == "Acme Corp"  # the snapshot didn't change underneath us
