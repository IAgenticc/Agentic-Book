from document_intelligence.schema import Clause, DocumentState, Obligation, PartyRecord
from document_intelligence.verification import all_verified, verify_document_state, verify_extraction

DOCUMENT = "Buyer shall pay Seller $10,000 within 30 days of delivery."


def test_verify_extraction_true_when_value_appears_verbatim():
    assert verify_extraction(DOCUMENT, "text", "pay Seller $10,000") is True


def test_verify_extraction_false_when_value_does_not_appear():
    assert verify_extraction(DOCUMENT, "text", "pay Seller $50,000") is False


def test_verify_extraction_false_for_empty_value():
    assert verify_extraction(DOCUMENT, "text", "") is False


def test_verify_extraction_tolerates_a_line_wrap_in_the_source():
    """Found live, against a real model and a real multi-line contract:
    the source document wraps a sentence across a line break, but a
    model quoting it back naturally normalizes the whitespace. An exact
    substring check would reject a real, correct quote as fabricated."""
    wrapped_document = "Consultant shall provide software consulting services to\nClient as described in Exhibit A."
    quoted_by_model = "Consultant shall provide software consulting services to Client as described in Exhibit A."
    assert verify_extraction(wrapped_document, "text", quoted_by_model) is True


def test_verify_extraction_still_rejects_a_genuinely_fabricated_quote():
    """Normalizing whitespace shouldn't widen the gate into accepting
    text that was never actually there."""
    assert verify_extraction(DOCUMENT, "text", "Seller shall pay Buyer $50,000") is False


def test_verify_extraction_tolerates_a_dash_underline_mid_sentence():
    """Found live against a real SEC filing: a section heading underlined
    with a run of dashes on its own line, positioned mid-sentence once
    the document is flattened to plain text. The model quoted the
    sentence correctly, without the dashes; an exact substring check
    rejected it as fabricated."""
    real_world_document = (
        "(a)  Assignment.  All  of  the  terms,  provisions  and  conditions of\n"
        "               ----------\n"
        "               this  Agreement  shall  be  binding  upon  and shall inure to the\n"
        "               benefit  of  and  be  enforceable by the parties hereto."
    )
    quoted_by_model = (
        "All of the terms, provisions and conditions of this Agreement shall be "
        "binding upon and shall inure to the benefit of and be enforceable by the parties hereto."
    )
    assert verify_extraction(real_world_document, "text", quoted_by_model) is True


def test_verify_document_state_flags_the_specific_field_that_fails():
    state = DocumentState(
        parties=[PartyRecord(name="Acme Corp", role="buyer")],
        obligations=[Obligation(party="Acme Corp", description="pay", source_clause="a fabricated clause")],
        clauses=[Clause(heading="Payment", text="Buyer shall pay Seller $10,000 within 30 days of delivery.")],
    )
    results = verify_document_state(DOCUMENT, state)
    assert results["parties"][0]["verified"] is False  # "Acme Corp" is not literally in this short document
    assert results["obligations"][0]["verified"] is False  # fabricated
    assert results["clauses"][0]["verified"] is True  # real, verbatim


def test_all_verified_true_only_when_every_field_passes():
    state = DocumentState(clauses=[Clause(heading="Payment", text="Buyer shall pay Seller $10,000 within 30 days of delivery.")])
    results = verify_document_state(DOCUMENT, state)
    assert all_verified(results) is True

    state.clauses.append(Clause(heading="Fake", text="a fabricated clause"))
    results = verify_document_state(DOCUMENT, state)
    assert all_verified(results) is False
