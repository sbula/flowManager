from unittest.mock import patch

import pytest

from workflow_core.knowledge.llm.gateway import LLMGateway
from workflow_core.knowledge.llm.provider import LLMProvider


# Mock Provider
class MockProvider(LLMProvider):
    def embed(self, texts, model):
        return [[0.1, 0.2] for _ in texts]

    def generate(self, prompt, model, **kwargs):
        return f"Response from {model}"


@pytest.fixture
def mock_config():
    return {
        "knowledge": {
            "embedding_provider": "gemini",
            "profiles": {
                "default": {"provider": "gemini", "model": "flash"},
                "coding": {"provider": "anthropic", "model": "claude-3.5"},
            },
        }
    }


def test_gateway_init(mock_config):
    with patch(
        "workflow_core.knowledge.llm.gateway.GeminiAdapter", return_value=MockProvider()
    ) as MockGemini, patch(
        "workflow_core.knowledge.llm.gateway.AnthropicAdapter",
        return_value=MockProvider(),
    ) as MockAnthropic, patch.dict(
        "os.environ", {"GOOGLE_API_KEY": "fake", "ANTHROPIC_API_KEY": "fake"}
    ):

        gateway = LLMGateway(mock_config)
        assert "gemini" in gateway.providers
        assert "anthropic" in gateway.providers


def test_gateway_routing(mock_config):
    with patch(
        "workflow_core.knowledge.llm.gateway.GeminiAdapter", return_value=MockProvider()
    ) as MockGemini, patch(
        "workflow_core.knowledge.llm.gateway.AnthropicAdapter",
        return_value=MockProvider(),
    ) as MockAnthropic, patch.dict(
        "os.environ", {"GOOGLE_API_KEY": "fake", "ANTHROPIC_API_KEY": "fake"}
    ):

        gateway = LLMGateway(mock_config)

        # Default
        resp = gateway.generate("test", profile="default")
        assert "flash" in resp

        # Coding
        resp = gateway.generate("code", profile="coding")
        assert "claude-3.5" in resp
