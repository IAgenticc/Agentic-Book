"""AnthropicModel had zero test coverage until this file -- not even a
mocked one. This doesn't replace a live smoke test (there's no API key
to run one with here), but it does exercise the real code path: request
shape, response parsing, and the ModelUnavailable error mapping, which a
live call alone wouldn't prove stays correct on every future edit.
"""
from unittest.mock import MagicMock, patch

import pytest

from sre_agent.models import AnthropicModel, ModelUnavailable


def test_generate_returns_the_response_text():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="restart the service")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("anthropic.Anthropic", return_value=fake_client):
        model = AnthropicModel(api_key="test-key")
        result = model.generate("what should I do?")

    assert result == "restart the service"
    fake_client.messages.create.assert_called_once()
    _, kwargs = fake_client.messages.create.call_args
    assert kwargs["messages"] == [{"role": "user", "content": "what should I do?"}]


def test_sdk_failure_is_mapped_to_model_unavailable():
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("connection reset")

    with patch("anthropic.Anthropic", return_value=fake_client):
        model = AnthropicModel(api_key="test-key")
        with pytest.raises(ModelUnavailable):
            model.generate("what should I do?")
