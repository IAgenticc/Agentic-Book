"""Mocked coverage for GeminiModel's real code path (request shape,
response parsing, error mapping) without a live network call. The live
path itself is proven separately by scripts/smoke_test_model_fallback.py
and scripts/smoke_test_openai_compatible.py.
"""
from unittest.mock import MagicMock, patch

import pytest

from sre_agent.models import GeminiModel, ModelUnavailable


def test_generate_returns_the_response_text():
    fake_response = MagicMock()
    fake_response.text = "restart the service"
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with patch("google.genai.Client", return_value=fake_client):
        model = GeminiModel(api_key="test-key")
        result = model.generate("what should I do?")

    assert result == "restart the service"
    fake_client.models.generate_content.assert_called_once_with(
        model="gemini-3.6-flash", contents="what should I do?"
    )


def test_sdk_failure_is_mapped_to_model_unavailable():
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = RuntimeError("connection reset")

    with patch("google.genai.Client", return_value=fake_client):
        model = GeminiModel(api_key="test-key")
        with pytest.raises(ModelUnavailable):
            model.generate("what should I do?")
