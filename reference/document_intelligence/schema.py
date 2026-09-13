"""Typed State (Chapter 36).

Every field that crosses a boundary between specialists gets an
explicit, validated schema. A specialist writing the wrong shape fails
immediately, at the point of the mistake, instead of three specialists
downstream.
"""
from __future__ import annotations

from pydantic import BaseModel


class PartyRecord(BaseModel):
    name: str
    role: str  # e.g. "buyer", "seller"


class Obligation(BaseModel):
    party: str
    description: str
    source_clause: str


class Clause(BaseModel):
    heading: str
    text: str


class DocumentState(BaseModel):
    parties: list[PartyRecord] = []
    obligations: list[Obligation] = []
    clauses: list[Clause] = []
