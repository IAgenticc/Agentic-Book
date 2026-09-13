"""Live smoke test proving OpenAICompatibleModel genuinely works: the
real `openai` SDK, unmodified, pointed at Gemini's OpenAI-compatible
endpoint instead of OpenAI's own. Same GEMINI_API_KEY as the other
Gemini smoke test.

Deliberately kept OUT of the pytest suite for the same reason as
smoke_test_model_fallback.py: real network calls don't belong in a fast,
deterministic, free test suite.

Usage:
    export GEMINI_API_KEY=$(cat ../.env)
    python scripts/smoke_test_openai_compatible.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sre_agent.models import OpenAICompatibleModel  # noqa: E402


def main() -> None:
    model = OpenAICompatibleModel(
        model="gemini-3.6-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.environ["GEMINI_API_KEY"],
    )
    result = model.generate("Reply with exactly one word: pong")
    print(f"text: {result!r}")
    assert result.strip().lower() == "pong"
    print("\nOK: the real openai SDK reached Gemini through its OpenAI-compatible endpoint.")


if __name__ == "__main__":
    main()
