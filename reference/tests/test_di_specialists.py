from agent_core.models import FakeModel
from document_intelligence.blackboard import Blackboard
from document_intelligence.specialists import clause_extraction, obligation_extraction, party_identification

CONTRACT = """This Agreement is entered into between Acme Corp ("Buyer") and
Widget Inc ("Seller"). Buyer shall pay Seller $10,000 within 30 days of
delivery."""


def test_party_identification_writes_typed_parties_to_the_board():
    model = FakeModel(
        responder=lambda p: '[{"name": "Acme Corp", "role": "buyer"}, {"name": "Widget Inc", "role": "seller"}]'
    )
    board = Blackboard()
    party_identification(model, CONTRACT, board)
    parties = board.read("parties")
    assert [p.name for p in parties] == ["Acme Corp", "Widget Inc"]
    assert parties[0].role == "buyer"


def test_specialist_raises_on_malformed_json_instead_of_writing_garbage():
    model = FakeModel(responder=lambda p: "this is not json")
    board = Blackboard()
    try:
        party_identification(model, CONTRACT, board)
        assert False, "expected a JSON parsing error"
    except Exception:
        pass
    assert board.read("parties") == []  # nothing got written


def test_specialist_handles_a_markdown_fenced_json_response():
    model = FakeModel(responder=lambda p: '```json\n[{"heading": "Payment", "text": "test"}]\n```')
    board = Blackboard()
    clause_extraction(model, CONTRACT, board)
    clauses = board.read("clauses")
    assert clauses[0].heading == "Payment"


def test_obligation_extraction_waits_for_parties_before_running():
    board = Blackboard()
    board.write("parties", [])  # simulate party_identification already having completed
    model = FakeModel(
        responder=lambda p: '[{"party": "Acme Corp", "description": "pay", "source_clause": "Buyer shall pay Seller $10,000 within 30 days of delivery."}]'
    )
    obligation_extraction(model, CONTRACT, board)
    obligations = board.read("obligations")
    assert obligations[0].party == "Acme Corp"
