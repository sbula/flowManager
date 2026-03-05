"""Gemini Adapter Contract Tests.

Tests the real GeminiProvider adapter against the full contract test suite
(CT-01 through CT-15) and Gemini-specific edge cases.

All SDK calls are mocked — these tests exercise the adapter code, not the API.
"""

from unittest.mock import MagicMock, patch

import pytest

from flow.llm.errors import (
    LLMAuthError,
    MissingDependencyError,
    ProviderAlreadyConfiguredError,
    ProviderConfigError,
    ProviderNotConfiguredError,
)

# Only import if the SDK is available
try:
    from flow.llm.adapters.gemini_adapter import GeminiProvider

    HAS_GEMINI_SDK = True
except (ImportError, MissingDependencyError):
    HAS_GEMINI_SDK = False


# Skip all tests if google-genai SDK is not installed
pytestmark = pytest.mark.skipif(
    not HAS_GEMINI_SDK,
    reason="google-genai SDK not installed",
)


def _mock_genai_client():
    """Create a mock google.genai.Client with realistic responses."""
    mock_client = MagicMock()

    # Mock generate_content response
    mock_response = MagicMock()
    mock_response.text = "Hello! I'm Gemini."
    mock_client.models.generate_content.return_value = mock_response

    # Mock embed_content response
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1] * 768
    mock_embed_response = MagicMock()
    mock_embed_response.embeddings = [mock_embedding]
    mock_client.models.embed_content.return_value = mock_embed_response

    # Mock count_tokens response
    mock_token_result = MagicMock()
    mock_token_result.total_tokens = 5
    mock_client.models.count_tokens.return_value = mock_token_result

    # Mock models.list response
    mock_client.models.list.return_value = [MagicMock(name="gemini-2.0-flash")]

    return mock_client


def _make_configured_provider(monkeypatch):
    """Create a configured GeminiProvider with mocked SDK."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-12345")

    mock_client = _mock_genai_client()

    with patch("flow.llm.adapters.gemini_adapter.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client

        # Need to also mock genai_types for Content/Part objects
        with patch("flow.llm.adapters.gemini_adapter.genai_types") as mock_types:
            mock_types.Content = MagicMock()
            mock_types.Part = MagicMock()
            mock_types.GenerateContentConfig = MagicMock()

            p = GeminiProvider()
            p.configure({"model": "gemini-2.0-flash", "auth": {"method": "api_key"}})
            # Store the mock client reference for later assertions
            p._mock_client = mock_client
            return p


# ─── Contract Tests (CT-01 to CT-15) ──────────────────────────────


class TestGeminiProviderContract:
    """Run the full contract test suite against GeminiProvider."""

    def test_ct_01_has_provider_name(self):
        """CT-01: provider_name is 'gemini'."""
        p = GeminiProvider()
        assert p.provider_name == "gemini"

    def test_ct_02_configure_succeeds(self, monkeypatch):
        """CT-02: configure() with valid config runs without error."""
        p = _make_configured_provider(monkeypatch)
        assert p._configured is True

    def test_ct_03_generate_after_configure(self, monkeypatch):
        """CT-03: generate() returns non-empty string."""
        p = _make_configured_provider(monkeypatch)
        with patch("flow.llm.adapters.gemini_adapter.genai_types") as mock_types:
            mock_types.Content = MagicMock()
            mock_types.Part = MagicMock()
            mock_types.GenerateContentConfig = MagicMock()
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
        p = GeminiProvider()
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
        p = GeminiProvider()
        p.close()

    def test_ct_15_invalid_role_rejected(self, monkeypatch):
        """CT-15: Invalid role -> ValueError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(ValueError):
            p.generate([{"role": "god", "content": "hi"}])


# ─── Gemini-Specific Tests ─────────────────────────────────────────


class TestGeminiSpecific:
    """Gemini adapter-specific edge cases."""

    def test_missing_sdk_raises_dependency_error(self, monkeypatch):
        """MissingDependencyError when SDK is None."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        p = GeminiProvider()
        with patch.object(
            type(p),
            "__module__",
            "flow.llm.adapters.gemini_adapter",
        ):
            import flow.llm.adapters.gemini_adapter as mod

            original_genai = mod.genai
            mod.genai = None
            try:
                with pytest.raises(MissingDependencyError):
                    p.configure({"model": "m", "auth": {"method": "api_key"}})
            finally:
                mod.genai = original_genai

    def test_missing_api_key(self, monkeypatch):
        """Missing GOOGLE_API_KEY -> LLMAuthError."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        p = GeminiProvider()
        with patch("flow.llm.adapters.gemini_adapter.genai") as mock_genai:  # noqa: F841
            with pytest.raises(LLMAuthError, match="GOOGLE_API_KEY"):
                p.configure({"model": "m", "auth": {"method": "api_key"}})

    def test_empty_api_key(self, monkeypatch):
        """Empty GOOGLE_API_KEY -> LLMAuthError."""
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        p = GeminiProvider()
        with patch("flow.llm.adapters.gemini_adapter.genai") as mock_genai:  # noqa: F841
            with pytest.raises(LLMAuthError):
                p.configure({"model": "m", "auth": {"method": "api_key"}})

    def test_missing_model_key(self):
        """Missing model -> ProviderConfigError."""
        p = GeminiProvider()
        with pytest.raises(ProviderConfigError, match="model"):
            p.configure({"auth": {"method": "none"}})

    def test_empty_model_name(self):
        """Empty model name -> ProviderConfigError."""
        p = GeminiProvider()
        with pytest.raises(ProviderConfigError, match="Empty"):
            p.configure({"model": "", "auth": {"method": "none"}})

    def test_embedding_dimensions(self, monkeypatch):
        """embedding_dimensions returns 768 when configured."""
        p = _make_configured_provider(monkeypatch)
        assert p.embedding_dimensions == 768

    def test_embedding_dimensions_none_when_unconfigured(self):
        """embedding_dimensions returns None when not configured."""
        p = GeminiProvider()
        assert p.embedding_dimensions is None

    def test_validate_uses_models_list(self, monkeypatch):
        """validate() uses models.list() — no token cost."""
        p = _make_configured_provider(monkeypatch)
        result = p.validate()
        assert result is True
        p._mock_client.models.list.assert_called()

    def test_validate_returns_false_on_error(self, monkeypatch):
        """validate() returns False when API unreachable."""
        p = _make_configured_provider(monkeypatch)
        p._mock_client.models.list.side_effect = Exception("unreachable")
        result = p.validate()
        assert result is False

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

    def test_unknown_auth_method(self, monkeypatch):
        """Unknown auth method -> ProviderConfigError."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        p = GeminiProvider()
        with patch("flow.llm.adapters.gemini_adapter.genai") as mock_genai:  # noqa: F841
            with pytest.raises(ProviderConfigError, match="Unknown auth"):
                p.configure({"model": "m", "auth": {"method": "oauth2_custom"}})

    def test_embed_empty_list(self, monkeypatch):
        """embed([]) -> [] without API call."""
        p = _make_configured_provider(monkeypatch)
        result = p.embed([])
        assert result == []

    def test_embed_none_input(self, monkeypatch):
        """embed(None) -> TypeError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(TypeError):
            p.embed(None)

    def test_embed_empty_string(self, monkeypatch):
        """embed([""]) -> ValueError."""
        p = _make_configured_provider(monkeypatch)
        with pytest.raises(ValueError, match="must not be empty"):
            p.embed([""])

    def test_credential_sanitization(self, monkeypatch):
        """Invisible chars in API key are stripped."""
        # Key with ZWSP, BOM, CRLF
        dirty_key = "\ufeff\u200bsk-abc\r\n123\t "
        monkeypatch.setenv("GOOGLE_API_KEY", dirty_key)
        p = GeminiProvider()
        with patch("flow.llm.adapters.gemini_adapter.genai") as mock_genai:
            mock_genai.Client.return_value = _mock_genai_client()
            p.configure({"model": "m", "auth": {"method": "api_key"}})
            # Verify cleaned key was passed
            call_args = mock_genai.Client.call_args
            used_key = call_args[1].get("api_key", "")
            assert "\ufeff" not in used_key
            assert "\u200b" not in used_key
            assert "\r" not in used_key
            assert "\n" not in used_key
            assert "\t" not in used_key
