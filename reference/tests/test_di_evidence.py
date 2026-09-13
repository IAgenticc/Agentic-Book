from agent_core.models import FakeModel
from document_intelligence.evidence import answer_with_evidence, parse_quote_and_answer

DOCUMENT = "Either party may terminate this Agreement with 60 days written notice."


def test_parse_quote_and_answer_splits_the_two_fields():
    response = "Quote: Either party may terminate this Agreement with 60 days written notice.\nAnswer: 60 days"
    quote, answer = parse_quote_and_answer(response)
    assert quote == "Either party may terminate this Agreement with 60 days written notice."
    assert answer == "60 days"


def test_parse_quote_and_answer_handles_none_quote():
    response = "Quote: none\nAnswer: not specified in this document"
    quote, answer = parse_quote_and_answer(response)
    assert quote is None
    assert answer == "not specified in this document"


def test_answer_with_evidence_returns_grounded_answer_when_quote_is_real():
    model = FakeModel(
        responder=lambda p: "Quote: Either party may terminate this Agreement with 60 days written notice.\nAnswer: 60 days"
    )
    result = answer_with_evidence(model, "What is the termination notice period?", DOCUMENT)
    assert result["answer"] == "60 days"
    assert result["quote"] in DOCUMENT


def test_answer_with_evidence_rejects_a_quote_not_actually_in_the_document():
    """This is the Chapter 30 failure mode this pattern exists to catch:
    a model claims a quote that isn't real -- fabricated evidence,
    not just a fabricated answer."""
    model = FakeModel(responder=lambda p: "Quote: This sentence does not exist in the document.\nAnswer: 30 days")
    result = answer_with_evidence(model, "What is the termination notice period?", DOCUMENT)
    assert result["answer"] is None
    assert result["reason"] == "quoted text not found in source"


def test_answer_with_evidence_accepts_a_genuine_not_specified_response():
    model = FakeModel(responder=lambda p: "Quote: none\nAnswer: not specified in this document")
    result = answer_with_evidence(model, "What is the governing law?", DOCUMENT)
    assert result["quote"] is None
    assert result["answer"] == "not specified in this document"
