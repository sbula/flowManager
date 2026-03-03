"""Anthropic Adapter Contract Tests.

Tests the real AnthropicProvider adapter against the full contract test suite
(CT-01 through CT-15) and Anthropic-specific edge cases.

All SDK calls are mocked — these tests exercise the adapter code, not the API.
"""

import os
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

from flow.llm.errors import (
    LLMAuthError,
    LLMConnectionError,
    LLMGenerationError,
    LLMRateLimitError,
    MissingDependencyError,
    ProviderAlreadyConfiguredError,
    ProviderConfigError,
    ProviderNotConfiguredError,
)
from flow.llm.provider import LLMProvider

# Only import if the SDK is available
try:
    from flow.llm.adapters.anthropic_adapter import AnthropicProvider

    HAS_ANTHROPIC_SDK = True
except (ImportError, MissingDependencyError):
    HAS_ANTHROPIC_SDK = False


# Skip all tests if anthropic SDK is not installed
pytestmark = pytest.mark.skipif(
    not HAS_ANTHROPIC_SDK,
    reason="anthropic SDK not installed",
)


def _mock_anthropic_client():
    """Create a mock anthropic.Anthropic client with realistic responses."""
    mock_client = MagicMock()

    # Mock messages.create response
    mock_text_block = MagicMock()
    mock_text_block.text = "Hello! I'm Claude."
    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_client.messages.create.return_value = mock_response

    # Mock count_tokens response
    mock_token_result = MagicMock()
    mock_token_result.input_tokens = 5
    mock_client.count_tokens.return_value = mock_token_result

    return mock_client


def _make_configured_provider(monkeypatch):
    """Create a configured AnthropicProvider with mocked SDK."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")

    mock_client = _mock_anthropic_client()

    with patch("flow.llm.adapters.anthropic_adapter.anthropic_sdk") as mock_sdk:
        mock_sdk.Anthropic.return_value = mock_client
        mock_sdk.NOT_GIVEN = MagicMock()  # Anthropic sentinel

        p = AnthropicProvider()
        p.configure(
            {
                "model": "claude-sonnet-4-20250514",
                "auth": {"method": "api_key"},
            }
        )
        # Store mock references for assertions
        p._mock_client = mock_client
        p._mock_sdk = mock_sdk
        return p


# ─── Contract Tests (CT-01 to CT-15) ──────────────────────────────


class TestAnthropicProviderContract:
    """Run the full contract test suite against AnthropicProvider."""

    def test_ct_01_has_provider_name(self):
        """CT-01: provider_name is 'anthropic'."""
        p = AnthropicProvider()
        assert p.provider_name == "anthropic"

    def test_ct_02_configure_succeeds(self, monkeypatch):
        """CT-02: configure() with valid config runs without error."""
        p = _make_configured_provider(monkeypatch)
        assert p._configured is True

    def test_ct_03_generate_after_configure(self, monkeypatch):
        """CT-03: generate() returns non-empty string."""
        p = _make_configured_provider(monkeypatch)
        with patch("flow.llm.adapters.anthropic_adapter.anthropic_sdk") as mock_sdk:
            mock_sdk.NOT_GIVEN = MagicMock()
            result = p.generate([{"role": "user", "content": "hello"}])
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_ct_04_count_tokens_after_configure(self, monkeypatch):
        """CT-04: count_tokens() returns int >= 0."""
        p = _make_configured_provider(monkeypatch)
        count = p.count_tokens("hello world")
        assert isinstance(count, int)
        assert count >= 0

    def test_ct_05_generate_before_configure(self):
        """CT-05: generate() before configure() -> ProviderNotConfiguredError."""
        p = AnthropicProvider()
        with pytest.raises(ProviderNotConfiguredError):
            p.generate([{"role": "user", "content": "hi"}])

    def test_ct_06_double_configure(self, monkeypatch):
        """CT-06: Double configure -> ProviderAlreadyConfiguredError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(ProviderAlreadyConfiguredError):
            p.configure({"model": "m", "auth": {"method": "api_key"}})

    def test_ct_07_close_idempotent(self, monkeypatch):
        """CT-07: close() is idempotent."""
        p = _make_configured_provider(monkeypatch)
        p.close()
        p.close()
        p.close()

    def test_ct_08_generate_after_close(self, monkeypatch):
        """CT-08: generate() after close() -> ProviderNotConfiguredError."""
        p = _make_configured_provider(monkeypatch)
        p.close()
        with pytest.raises(ProviderNotConfiguredError):
            p.generate([{"role": "user", "content": "hi"}])

    def test_ct_09_configure_after_close(self, monkeypatch):
        """CT-09: configure() after close() -> ProviderAlreadyConfiguredError."""
        p = _make_configured_provider(monkeypatch)
        p.close()
        with pytest.raises(ProviderAlreadyConfiguredError):
            p.configure({"model": "m"})

    def test_ct_10_empty_messages_rejected(self, monkeypatch):
        """CT-10: generate([]) -> ValueError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(ValueError):
            p.generate([])

    def test_ct_11_none_messages_rejected(self, monkeypatch):
        """CT-11: generate(None) -> ValueError or TypeError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises((ValueError, TypeError)):
            p.generate(None)

    def test_ct_12_count_tokens_type_check(self, monkeypatch):
        """CT-12: count_tokens(42) -> TypeError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(TypeError):
            p.count_tokens(42)

    def test_ct_13_count_tokens_empty_string(self, monkeypatch):
        """CT-13: count_tokens("") -> 0."""
        p = _make_configured_provider(monkeypatch)
        assert p.count_tokens("") == 0

    def test_ct_14_close_without_configure(self):
        """CT-14: close() without configure() -> no error."""
        p = AnthropicProvider()
        p.close()

    def test_ct_15_invalid_role_rejected(self, monkeypatch):
        """CT-15: Invalid role -> ValueError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(ValueError):
            p.generate([{"role": "god", "content": "hi"}])


# ─── Anthropic-Specific Tests ──────────────────────────────────────


class TestAnthropicSpecific:
    """Anthropic adapter-specific edge cases."""

    def test_embed_raises_not_implemented(self, monkeypatch):
        """Anthropic does not support embeddings."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(NotImplementedError, match="does not support"):
            p.embed(["hello"])

    def test_embedding_dimensions_none(self):
        """embedding_dimensions always None for Anthropic."""
        p = AnthropicProvider()
        assert p.embedding_dimensions is None

    def test_missing_sdk_raises_dependency_error(self, monkeypatch):
        """MissingDependencyError when SDK is None."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        p = AnthropicProvider()
        import flow.llm.adapters.anthropic_adapter as mod

        original_sdk = mod.anthropic_sdk
        mod.anthropic_sdk = None
        try:
            with pytest.raises(MissingDependencyError):
                p.configure({"model": "m", "auth": {"method": "api_key"}})
        finally:
            mod.anthropic_sdk = original_sdk

    def test_missing_api_key(self, monkeypatch):
        """Missing ANTHROPIC_API_KEY -> LLMAuthError."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        p = AnthropicProvider()
        with patch("flow.llm.adapters.anthropic_adapter.anthropic_sdk"):
            with pytest.raises(LLMAuthError, match="ANTHROPIC_API_KEY"):
                p.configure({"model": "m", "auth": {"method": "api_key"}})

    def test_empty_api_key(self, monkeypatch):
        """Empty ANTHROPIC_API_KEY -> LLMAuthError."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        p = AnthropicProvider()
        with patch("flow.llm.adapters.anthropic_adapter.anthropic_sdk"):
            with pytest.raises(LLMAuthError):
                p.configure({"model": "m", "auth": {"method": "api_key"}})

    def test_missing_model_key(self):
        """Missing model -> ProviderConfigError."""
        p = AnthropicProvider()
        with pytest.raises(ProviderConfigError, match="model"):
            p.configure({"auth": {"method": "api_key"}})

    def test_empty_model_name(self):
        """Empty model name -> ProviderConfigError."""
        p = AnthropicProvider()
        with pytest.raises(ProviderConfigError, match="Empty"):
            p.configure({"model": "", "auth": {"method": "api_key"}})

    def test_adc_not_supported(self, monkeypatch):
        """ADC auth method -> ProviderConfigError."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        p = AnthropicProvider()
        with pytest.raises(ProviderConfigError, match="not supported"):
            p.configure({"model": "m", "auth": {"method": "adc"}})

    def test_none_auth_method_rejected(self, monkeypatch):
        """method='none' -> ProviderConfigError (Anthropic requires auth)."""
        p = AnthropicProvider()
        with pytest.raises(ProviderConfigError, match="requires authentication"):
            p.configure({"model": "m", "auth": {"method": "none"}})

    def test_timeout_zero(self, monkeypatch):
        """timeout_seconds=0 -> immediate TimeoutError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(TimeoutError):
            p.generate([{"role": "user", "content": "hi"}], timeout_seconds=0)

    def test_negative_timeout(self, monkeypatch):
        """timeout_seconds=-1 -> ValueError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(ValueError, match="negative"):
            p.generate([{"role": "user", "content": "hi"}], timeout_seconds=-1)

    def test_credential_sanitization(self, monkeypatch):
        """Invisible chars in API key are stripped."""
        dirty_key = "\ufeff\u200bsk-abc\r\n123\t "
        monkeypatch.setenv("ANTHROPIC_API_KEY", dirty_key)
        p = AnthropicProvider()
        with patch("flow.llm.adapters.anthropic_adapter.anthropic_sdk") as mock_sdk:
            mock_sdk.Anthropic.return_value = _mock_anthropic_client()
            p.configure({"model": "m", "auth": {"method": "api_key"}})
            call_args = mock_sdk.Anthropic.call_args
            used_key = call_args[1].get("api_key", "")
            assert "\ufeff" not in used_key
            assert "\u200b" not in used_key
            assert "\r" not in used_key
            assert "\n" not in used_key
            assert "\t" not in used_key

    def test_close_releases_client(self, monkeypatch):
        """close() calls client.close() and clears reference."""
        p = _make_configured_provider(monkeypatch)
        mock_client = p._client
        p.close()
        assert p._client is None
        assert p._closed is True
        mock_client.close.assert_called_once()

    def test_system_message_handling(self, monkeypatch):
        """System messages are extracted and passed separately."""
        p = _make_configured_provider(monkeypatch)
        with patch("flow.llm.adapters.anthropic_adapter.anthropic_sdk") as mock_sdk:
            mock_sdk.NOT_GIVEN = MagicMock()
            p.generate(
                [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello!"},
                ]
            )
        # Verify create was called (system message extracted)
        p._mock_client.messages.create.assert_called()
