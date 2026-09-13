"""Re-exports agent_core.models so existing `from sre_agent.models import
...` imports (including this package's own modules and its tests) keep
working after the model interface moved to the shared agent_core package
-- both sre_agent and document_intelligence need the same one."""
from agent_core.models import (  # noqa: F401
    AnthropicModel,
    FakeModel,
    GeminiModel,
    Model,
    ModelUnavailable,
    OpenAICompatibleModel,
    call_with_fallback,
)
