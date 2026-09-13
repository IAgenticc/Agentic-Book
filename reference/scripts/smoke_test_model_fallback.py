"""Live smoke test for Chapter 26's Model Fallback, using a real second
provider (Gemini, via the official google-genai SDK) instead of FakeModel.

Deliberately kept OUT of the pytest suite: the rest of the test suite must
stay fast, free, and deterministic, which a real network call to a live
model API is none of. Run this by hand when you want to confirm the
fallback chain actually reaches a real provider, not as part of CI.

Usage:
    export GEMINI_API_KEY=$(cat ../.env)
    python scripts/smoke_test_model_fallback.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sre_agent.models import FakeModel, GeminiModel, call_with_fallback  # noqa: E402


def main() -> None:
    primary = FakeModel(fail=True)  # simulates Chapter 26's "primary is down"
    fallback = GeminiModel()  # the real google-genai SDK, a real, different provider

    result = call_with_fallback(
        prompt="Reply with exactly one word: pong",
        primary=primary,
        fallback=fallback,
        degraded=lambda _prompt: {"text": "degraded", "source": "degraded"},
    )

    print(f"source: {result['source']}")
    print(f"text:   {result['text']!r}")
    assert result["source"] == "model", "expected the real fallback to serve this, not degraded mode"
    print("\nOK: primary failed, fallback (a real, live model via google-genai) served the request.")


if __name__ == "__main__":
    main()
