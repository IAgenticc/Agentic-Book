from agent_core.models import FakeModel
from document_intelligence.orchestrator import process_document
from document_intelligence.risk import DocumentMetadata

CONTRACT = (
    'This Agreement is entered into between Acme Corp ("Buyer") and Widget Inc '
    '("Seller"). Buyer shall pay Seller $10,000 within 30 days of delivery.'
)


def fake_responder(prompt: str) -> str:
    if "named party" in prompt:
        return '[{"name": "Acme Corp", "role": "buyer"}, {"name": "Widget Inc", "role": "seller"}]'
    if "obligations" in prompt:
        return (
            '[{"party": "Acme Corp", "description": "pay for goods", '
            '"source_clause": "Buyer shall pay Seller $10,000 within 30 days of delivery."}]'
        )
    if "distinct clauses" in prompt:
        return '[{"heading": "Payment", "text": "Buyer shall pay Seller $10,000 within 30 days of delivery."}]'
    raise AssertionError(f"unexpected prompt: {prompt[:80]}")


def test_process_document_runs_all_three_specialists_and_verifies_results():
    model = FakeModel(responder=fake_responder)
    result = process_document(model, CONTRACT, DocumentMetadata())

    assert [p.name for p in result["state"].parties] == ["Acme Corp", "Widget Inc"]
    assert result["state"].obligations[0].party == "Acme Corp"
    assert result["state"].clauses[0].heading == "Payment"
    assert result["verified"] is True
    assert result["risk_tier"] == "low"


def test_process_document_flags_unverified_facts_without_discarding_the_rest():
    def responder_with_one_fabrication(prompt: str) -> str:
        if "named party" in prompt:
            return '[{"name": "Ghost Corp", "role": "buyer"}]'  # not in the document at all
        if "obligations" in prompt:
            return '[]'
        if "distinct clauses" in prompt:
            return '[{"heading": "Payment", "text": "Buyer shall pay Seller $10,000 within 30 days of delivery."}]'
        raise AssertionError(prompt)

    model = FakeModel(responder=responder_with_one_fabrication)
    result = process_document(model, CONTRACT, DocumentMetadata())

    assert result["verified"] is False
    assert result["verification"]["parties"][0]["verified"] is False
    assert result["verification"]["clauses"][0]["verified"] is True  # unaffected by the other field's failure


def test_process_document_reports_the_risk_tier():
    model = FakeModel(responder=fake_responder)
    result = process_document(model, CONTRACT, DocumentMetadata(contains_pii=True))
    assert result["risk_tier"] == "medium"
