"""Real HTTP-level tests for document_intelligence/api.py, using FastAPI's
TestClient (a genuine ASGI request/response cycle, not a mock of the
transport layer). Appendix C walks through each of these scenarios by
hand with curl and Swagger; these are the same scenarios kept as
permanent regression tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent_core.models import FakeModel, ModelUnavailable
from document_intelligence.api import app

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
    if "Quote:" in prompt or "exact sentence" in prompt:
        return (
            "Quote: Buyer shall pay Seller $10,000 within 30 days of delivery.\n"
            "Answer: Within 30 days of delivery."
        )
    raise AssertionError(f"unexpected prompt: {prompt[:80]}")


def test_processes_a_real_contract_end_to_end():
    with TestClient(app) as client:
        app.state.model = FakeModel(responder=fake_responder)
        resp = client.post("/documents", json={"document": CONTRACT})
        assert resp.status_code == 200
        body = resp.json()
        assert body["verified"] is True
        assert body["risk_tier"] == "low"
        assert [p["name"] for p in body["state"]["parties"]] == ["Acme Corp", "Widget Inc"]


def test_pii_metadata_raises_the_risk_tier():
    with TestClient(app) as client:
        app.state.model = FakeModel(responder=fake_responder)
        resp = client.post(
            "/documents", json={"document": CONTRACT, "contains_pii": True}
        )
        assert resp.json()["risk_tier"] == "medium"


def test_question_returns_an_evidence_backed_answer():
    with TestClient(app) as client:
        app.state.model = FakeModel(responder=fake_responder)
        resp = client.post(
            "/documents",
            json={"document": CONTRACT, "question": "When is payment due?"},
        )
        evidence = resp.json()["evidence"]
        assert evidence["quote"] in CONTRACT
        assert "30 days" in evidence["answer"]


def test_fabricated_quote_is_rejected_even_with_a_real_sounding_answer():
    def responder_with_a_fabricated_quote(prompt: str) -> str:
        if "Quote:" in prompt or "exact sentence" in prompt:
            return "Quote: Buyer shall pay Seller $999,999,999.\nAnswer: $999,999,999."
        return fake_responder(prompt)

    with TestClient(app) as client:
        app.state.model = FakeModel(responder=responder_with_a_fabricated_quote)
        resp = client.post(
            "/documents",
            json={"document": CONTRACT, "question": "How much is owed?"},
        )
        evidence = resp.json()["evidence"]
        assert evidence["answer"] is None
        assert evidence["reason"] == "quoted text not found in source"


def test_malformed_request_is_422():
    with TestClient(app) as client:
        resp = client.post("/documents", json={})
        assert resp.status_code == 422


def test_no_model_configured_is_503():
    with TestClient(app) as client:
        app.state.model = None
        resp = client.post("/documents", json={"document": CONTRACT})
        assert resp.status_code == 503


def test_a_broken_specialist_is_502_not_a_silent_partial_result():
    # Only clause_extraction fails here, deliberately: it has no dependency
    # on "parties", so this fails fast instead of waiting out
    # obligation_extraction's ten-second board.wait_for timeout too.
    def clause_extraction_fails(prompt: str) -> str:
        if "distinct clauses" in prompt:
            raise ModelUnavailable("simulated outage")
        return fake_responder(prompt)

    with TestClient(app) as client:
        app.state.model = FakeModel(responder=clause_extraction_fails)
        resp = client.post("/documents", json={"document": CONTRACT})
        assert resp.status_code == 502
