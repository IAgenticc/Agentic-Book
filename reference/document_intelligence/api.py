"""A minimal FastAPI wrapper around process_document and
answer_with_evidence (Chapter 42's orchestrator), exposing the Document
Intelligence Agent through a real HTTP interface instead of a direct
Python call."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent_core.models import GeminiModel, ModelUnavailable

from .evidence import answer_with_evidence
from .orchestrator import SpecialistFailure, process_document
from .risk import DocumentMetadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.model = GeminiModel()
    except Exception:  # noqa: BLE001 -- no key yet; surfaced as a clean 503 per request
        app.state.model = None
    yield


app = FastAPI(title="Document Intelligence Agent API", version="1.0.0", lifespan=lifespan)


class DocumentRequest(BaseModel):
    document: str
    question: str | None = None
    contains_pii: bool = False
    crosses_data_boundary: bool = False
    legal_hold: bool = False


@app.post("/documents")
def process(req: DocumentRequest):
    if app.state.model is None:
        raise HTTPException(status_code=503, detail="no model configured: set GEMINI_API_KEY")

    metadata = DocumentMetadata(
        contains_pii=req.contains_pii,
        crosses_data_boundary=req.crosses_data_boundary,
        legal_hold=req.legal_hold,
    )
    try:
        result = process_document(app.state.model, req.document, metadata)
    except SpecialistFailure as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if req.question:
        try:
            result["evidence"] = answer_with_evidence(
                app.state.model, req.question, req.document
            )
        except ModelUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return result
