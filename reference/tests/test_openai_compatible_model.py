"""Mocked coverage for OpenAICompatibleModel's real code path. The live
path is proven separately by scripts/smoke_test_openai_compatible.py,
which points the real openai SDK at Gemini's compatible endpoint.
"""
from unittest.mock import MagicMock, patch

import pytest

from sre_agent.models import ModelUnavailable, OpenAICompatibleModel


def test_generate_returns_the_response_text():
    fake_message = MagicMock()
    fake_message.content = "restart the service"
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    with patch("openai.OpenAI", return_value=fake_client):
        model = OpenAICompatibleModel(model="gpt-4o-mini", base_url="https://api.openai.com/v1", api_key="test-key")
        result = model.generate("what should I do?")

    assert result == "restart the service"
    fake_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "what should I do?"}],
    )


def test_sdk_failure_is_mapped_to_model_unavailable():
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("connection reset")

    with patch("openai.OpenAI", return_value=fake_client):
        model = OpenAICompatibleModel(model="gpt-4o-mini", base_url="https://api.openai.com/v1", api_key="test-key")
        with pytest.raises(ModelUnavailable):
            model.generate("what should I do?")
