"""Model interface and Model Fallback (Chapter 26).

A Model is anything with a `generate(prompt: str) -> str` method. Real code
talks to Claude through AnthropicModel; tests and the demo CLI use FakeModel
so nothing here requires a live API key to run.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol


class ModelUnavailable(Exception):
    """Raised when a model cannot serve a request at all (not just slowly)."""


class Model(Protocol):
    def generate(self, prompt: str) -> str: ...


@dataclass
class FakeModel:
    """Deterministic stand-in model for tests and the demo CLI.

    `responder` maps a prompt to a canned response. `fail` forces every
    call to raise ModelUnavailable, for exercising Chapter 26's fallback
    and Chapter 27's circuit breaker without touching a real API.
    """

    responder: Callable[[str], str] = field(default=lambda prompt: "ok")
    fail: bool = False
    calls: int = field(default=0, init=False)

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.fail:
            raise ModelUnavailable("FakeModel configured to fail")
        return self.responder(prompt)


class AnthropicModel:
    """Thin wrapper around the Anthropic SDK. Imported lazily so the rest
    of this package works without the `anthropic` package installed."""

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None):
        import anthropic  # noqa: PLC0415 (intentional lazy import)

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:  # narrow this in production to the SDK's own error types
            raise ModelUnavailable(str(exc)) from exc


class GeminiModel:
    """Thin wrapper around the official Google GenAI SDK (`google-genai`)
   : Chapter 26's concrete "different provider" fallback alongside
    AnthropicModel. Imported lazily, same as AnthropicModel, so the rest
    of this package works without the `google-genai` package installed."""

    def __init__(self, model: str = "gemini-3.6-flash", api_key: str | None = None):
        from google import genai  # noqa: PLC0415 (intentional lazy import)

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(model=self._model, contents=prompt)
            return response.text
        except Exception as exc:  # narrow this in production to the SDK's own error types
            raise ModelUnavailable(str(exc)) from exc


class OpenAICompatibleModel:
    """Wraps the real `openai` SDK pointed at any provider that exposes an
    OpenAI-compatible chat-completions endpoint: Gemini does
    (`https://generativelanguage.googleapis.com/v1beta/openai/`), and so
    do several others. One class covers all of them: only base_url and
    model change, confirmed working end-to-end against a live Gemini key.
    Imported lazily, same as AnthropicModel and GeminiModel."""

    def __init__(self, model: str, base_url: str, api_key: str | None = None):
        from openai import OpenAI  # noqa: PLC0415 (intentional lazy import)

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def generate(self, prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as exc:  # narrow this in production to the SDK's own error types
            raise ModelUnavailable(str(exc)) from exc


def call_with_fallback(
    prompt: str,
    primary: Model,
    fallback: Model,
    degraded: Callable[[str], dict],
    primary_timeout: float = 5.0,
    fallback_timeout: float = 10.0,
) -> dict:
    """Chapter 26: try primary, then fallback, then a no-model degraded response.

    Timeouts are honored on a best-effort basis here since FakeModel calls
    return instantly; a real deployment would enforce them at the HTTP
    client level (e.g. httpx timeout on the Anthropic client).
    """
    for model, _timeout in ((primary, primary_timeout), (fallback, fallback_timeout)):
        start = time.monotonic()
        try:
            text = model.generate(prompt)
            return {"text": text, "source": "model", "elapsed": time.monotonic() - start}
        except ModelUnavailable:
            continue
    return degraded(prompt)
