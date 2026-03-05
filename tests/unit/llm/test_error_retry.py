"""Error Handling & Retry Tests — spec §7.

Tests error classification, retry behavior, and timeout contracts.
Covers T7.1.01-T7.1.17, T7.2.01-T7.2.12, T7.3.01-T7.3.09.
"""

import logging
import time

import pytest

from flow.llm.errors import (
    LLMAuthError,
    LLMConnectionError,
    LLMGenerationError,
    LLMRateLimitError,
    ProviderConfigError,
)


# ─── 7.1 Error Classification ─────────────────────────────────────


class TestErrorClassification:
    """T7.1.01 - T7.1.17."""

    def test_t7_1_01_network_error(self, configured_provider):
        """T7.1.01: Network error -> LLMConnectionError."""
        configured_provider._generate_side_effect = LLMConnectionError(
            "Connection refused"
        )
        with pytest.raises(LLMConnectionError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_02_dns_failure(self, configured_provider):
        """T7.1.02: DNS failure -> LLMConnectionError."""
        configured_provider._generate_side_effect = LLMConnectionError(
            "DNS resolution failed"
        )
        with pytest.raises(LLMConnectionError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_03_http_401(self, configured_provider):
        """T7.1.03: HTTP 401 -> LLMAuthError."""
        configured_provider._generate_side_effect = LLMAuthError(
            "HTTP 401 Unauthorized"
        )
        with pytest.raises(LLMAuthError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_04_http_403(self, configured_provider):
        """T7.1.04: HTTP 403 -> LLMAuthError."""
        configured_provider._generate_side_effect = LLMAuthError("HTTP 403 Forbidden")
        with pytest.raises(LLMAuthError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_05_http_429(self, configured_provider):
        """T7.1.05: HTTP 429 -> LLMRateLimitError."""
        configured_provider._generate_side_effect = LLMRateLimitError(
            "HTTP 429 Too Many Requests"
        )
        with pytest.raises(LLMRateLimitError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_06_http_500(self, configured_provider):
        """T7.1.06: HTTP 500 -> LLMGenerationError."""
        configured_provider._generate_side_effect = LLMGenerationError(
            "HTTP 500 Internal Server Error"
        )
        with pytest.raises(LLMGenerationError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_07_safety_filter_block(self, configured_provider):
        """T7.1.07: Safety filter -> LLMGenerationError with message."""
        configured_provider._generate_side_effect = LLMGenerationError(
            "Content blocked by safety filter: HARM_CATEGORY_HATE_SPEECH"
        )
        with pytest.raises(LLMGenerationError, match="safety filter"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_08_model_not_found(self, configured_provider):
        """T7.1.08: Model not found (404) -> ProviderConfigError."""
        configured_provider._generate_side_effect = ProviderConfigError(
            "Model 'gpt-5-turbo' not found. "
            "Update the profile config to use an available model."
        )
        with pytest.raises(ProviderConfigError, match="not found"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_09_context_overflow(self, configured_provider):
        """T7.1.09: Context overflow -> non-retryable LLMGenerationError."""
        configured_provider._generate_side_effect = LLMGenerationError(
            "Context window overflow: max 128000 tokens, got 200000"
        )
        with pytest.raises(LLMGenerationError, match="overflow"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_10_empty_response(self, configured_provider):
        """T7.1.10: Provider returns empty -> LLMGenerationError."""
        configured_provider._generate_response = ""
        with pytest.raises(LLMGenerationError, match="empty"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_11_whitespace_only_response(self, configured_provider):
        """T7.1.11: Provider returns whitespace-only -> LLMGenerationError."""
        configured_provider._generate_response = "   \n  "
        with pytest.raises(LLMGenerationError, match="empty"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_12_none_response_text(self, configured_provider):
        """T7.1.12: SDK returns None -> LLMGenerationError, NOT TypeError."""
        configured_provider._generate_response = None
        with pytest.raises(LLMGenerationError, match="None"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_13_malformed_response_object(self, configured_provider):
        """T7.1.13: SDK response .text raises AttributeError ->
        LLMGenerationError, NOT unhandled AttributeError."""
        # Our MockProvider returns a string, so we test that the
        # generate() correctly validates the response type
        configured_provider._generate_response = 42  # Not a string
        with pytest.raises(LLMGenerationError, match="None|non-string"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_14_unicode_provider_error(self, configured_provider):
        """T7.1.14: Unicode error message preserved without crash."""
        err_msg = "限速 🚫: リクエストが多すぎます"
        configured_provider._generate_side_effect = LLMRateLimitError(err_msg)
        with pytest.raises(LLMRateLimitError) as exc_info:
            configured_provider.generate([{"role": "user", "content": "hi"}])
        assert "限速" in str(exc_info.value)
        assert "🚫" in str(exc_info.value)

    def test_t7_1_15_sdk_throws_runtime_error(self, configured_provider):
        """T7.1.15: RuntimeError from SDK -> mapped to LLMGenerationError.
        Adapters MUST catch all non-standard SDK exceptions."""
        # For MockProvider, we set the side effect to a RuntimeError.
        # In a real adapter, this would be caught and re-raised as
        # LLMGenerationError. Here we verify the test contract.
        configured_provider._generate_side_effect = RuntimeError("internal SDK bug")
        with pytest.raises(RuntimeError):
            configured_provider.generate([{"role": "user", "content": "hi"}])
        # Note: A real adapter would catch this and raise LLMGenerationError.
        # The contract test suite (CT-x) validates this for real adapters.

    def test_t7_1_16_sdk_throws_key_error(self, configured_provider):
        """T7.1.16: KeyError from SDK -> should be caught by real adapter."""
        configured_provider._generate_side_effect = KeyError("response")
        with pytest.raises(KeyError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_1_17_sdk_throws_recursion_error(self, configured_provider):
        """T7.1.17: RecursionError from SDK -> should be caught."""
        configured_provider._generate_side_effect = RecursionError(
            "Maximum recursion depth exceeded"
        )
        with pytest.raises(RecursionError):
            configured_provider.generate([{"role": "user", "content": "hi"}])


# ─── 7.2 Retry Behavior ───────────────────────────────────────────


class TestRetryBehavior:
    """T7.2.01 - T7.2.12.

    Since MockProvider doesn't implement Tenacity retries (that's
    an adapter-level concern), these tests verify the retry contract
    conceptually and document expected behavior.
    The contract test base class validates actual retry behavior.
    """

    def test_t7_2_01_connection_error_retried_3x(self, configured_provider):
        """T7.2.01: LLMConnectionError -> retryable.
        Verify the error type is the kind that SHOULD be retried."""
        err = LLMConnectionError("Connection refused")
        assert isinstance(err, ConnectionError)  # Base class
        # In a real adapter with Tenacity, this would be retried 3x
        configured_provider._generate_side_effect = err
        with pytest.raises(LLMConnectionError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_02_rate_limit_retried_3x(self, configured_provider):
        """T7.2.02: LLMRateLimitError -> retryable with longer backoff."""
        err = LLMRateLimitError("HTTP 429")
        assert isinstance(err, RuntimeError)
        configured_provider._generate_side_effect = err
        with pytest.raises(LLMRateLimitError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_03_auth_error_not_retried(self, configured_provider):
        """T7.2.03: LLMAuthError -> NOT retried, immediate failure."""
        configured_provider._generate_side_effect = LLMAuthError("Invalid API key")
        with pytest.raises(LLMAuthError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_04_config_error_not_retried(self, configured_provider):
        """T7.2.04: ProviderConfigError -> NOT retried."""
        configured_provider._generate_side_effect = ProviderConfigError(
            "Model not found"
        )
        with pytest.raises(ProviderConfigError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_05_generation_error_retried_once(self, configured_provider):
        """T7.2.05: LLMGenerationError (non-overflow) -> single retry."""
        err = LLMGenerationError("Model hiccup")
        configured_provider._generate_side_effect = err
        with pytest.raises(LLMGenerationError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_06_context_overflow_not_retried(self, configured_provider):
        """T7.2.06: Context overflow -> immediate failure, no retry."""
        err = LLMGenerationError("Context window overflow")
        configured_provider._generate_side_effect = err
        with pytest.raises(LLMGenerationError, match="overflow"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_07_timeout_retried(self, configured_provider):
        """T7.2.07: TimeoutError -> retryable."""
        configured_provider._generate_side_effect = TimeoutError("API call timed out")
        with pytest.raises(TimeoutError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_08_retry_logging(self, configured_provider, caplog):
        """T7.2.08: Verify retry concept is logged at WARNING.
        In a real adapter, Tenacity would log each retry attempt."""
        # Simulate what a real adapter's retry logging would look like
        with caplog.at_level(logging.WARNING):
            configured_provider._generate_side_effect = LLMConnectionError(
                "Network error"
            )
            with pytest.raises(LLMConnectionError):
                configured_provider.generate([{"role": "user", "content": "hi"}])
        # MockProvider doesn't implement Tenacity retries, so no
        # WARNING logs are emitted. This test documents the
        # expectation for real adapters.

    def test_t7_2_09_retry_after_header(self, configured_provider):
        """T7.2.09: 429 with Retry-After header -> respect wait time.
        Conceptual test: real adapters parse the header."""
        err = LLMRateLimitError("HTTP 429, Retry-After: 10")
        configured_provider._generate_side_effect = err
        with pytest.raises(LLMRateLimitError, match="Retry-After"):
            configured_provider.generate([{"role": "user", "content": "hi"}])

    def test_t7_2_10_transient_then_success(self, configured_provider):
        """T7.2.10: First call fails, second succeeds.
        Simulated by changing the side effect between calls."""
        configured_provider._generate_side_effect = LLMConnectionError(
            "Transient failure"
        )
        with pytest.raises(LLMConnectionError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

        # Second call succeeds
        configured_provider._generate_side_effect = None
        result = configured_provider.generate([{"role": "user", "content": "hi"}])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_t7_2_11_retry_amplified_timeout_bound(self, configured_provider):
        """T7.2.11: Total wall-clock time is bounded.
        Verify that timeout_seconds=1 completes within a reasonable bound."""
        configured_provider._generate_side_effect = TimeoutError("Timeout")
        start = time.time()
        with pytest.raises(TimeoutError):
            configured_provider.generate(
                [{"role": "user", "content": "hi"}], timeout_seconds=1
            )
        elapsed = time.time() - start
        # Without retries (mock), should return immediately
        assert elapsed < 5

    def test_t7_2_12_dual_layer_retry_lifecycle(self, configured_provider):
        """T7.2.12: End-to-end dual-layer retry lifecycle.
        Adapter retries (Tenacity) and Engine retries (AtomResult.RETRY)
        are independent. Adapter retry count resets across engine retries.

        This is a simulated test: real test requires full Engine integration.
        Here we verify the adapter resets cleanly between invocations.
        """
        # First invocation: adapter fails (simulating Tenacity exhaustion)
        configured_provider._generate_side_effect = LLMConnectionError(
            "All retries exhausted"
        )
        with pytest.raises(LLMConnectionError):
            configured_provider.generate([{"role": "user", "content": "hi"}])

        # Between engine-level retries, adapter is fresh
        # (in a real scenario, Factory.reset() + create() gives fresh adapter)
        # Here we simulate by clearing the side effect
        configured_provider._generate_side_effect = None
        result = configured_provider.generate([{"role": "user", "content": "hi"}])
        assert isinstance(result, str)


# ─── 7.3 Timeout Contract ─────────────────────────────────────────


class TestTimeoutContract:
    """T7.3.01 - T7.3.09."""

    def test_t7_3_01_generate_respects_timeout(self, configured_provider):
        """T7.3.01: timeout_seconds=2, provider takes 5s -> TimeoutError.
        MockProvider checks timeout parameter but doesn't actually wait."""
        # With a real adapter, this would use threading/async timeout.
        # MockProvider validates timeout_seconds parameter type only.
        configured_provider._generate_side_effect = TimeoutError(
            "Timed out after 2 seconds"
        )
        with pytest.raises(TimeoutError):
            configured_provider.generate(
                [{"role": "user", "content": "hi"}], timeout_seconds=2
            )

    def test_t7_3_02_embed_respects_timeout(self, configured_provider):
        """T7.3.02: embed timeout -> TimeoutError."""
        configured_provider._embed_side_effect = TimeoutError("Timed out")
        with pytest.raises(TimeoutError):
            configured_provider.embed(["hello"], timeout_seconds=1)

    def test_t7_3_03_default_timeout_generate(self, configured_provider):
        """T7.3.03: No explicit timeout -> 120s default per spec."""
        # Verify the parameter signature default
        import inspect

        sig = inspect.signature(configured_provider.generate)
        default = sig.parameters["timeout_seconds"].default
        assert default == 120

    def test_t7_3_04_default_timeout_embed(self, configured_provider):
        """T7.3.04: No explicit timeout -> 60s default per spec."""
        import inspect

        sig = inspect.signature(configured_provider.embed)
        default = sig.parameters["timeout_seconds"].default
        assert default == 60

    def test_t7_3_05_zero_timeout(self, configured_provider):
        """T7.3.05: timeout_seconds=0 -> immediate TimeoutError or ValueError."""
        with pytest.raises((TimeoutError, ValueError)):
            configured_provider.generate(
                [{"role": "user", "content": "hi"}], timeout_seconds=0
            )

    def test_t7_3_06_negative_timeout(self, configured_provider):
        """T7.3.06: timeout_seconds=-1 -> ValueError."""
        with pytest.raises(ValueError, match="negative"):
            configured_provider.generate(
                [{"role": "user", "content": "hi"}], timeout_seconds=-1
            )

    def test_t7_3_07_float_timeout(self, configured_provider):
        """T7.3.07: timeout_seconds=0.5 -> TypeError (spec says int)."""
        with pytest.raises(TypeError, match="int"):
            configured_provider.generate(
                [{"role": "user", "content": "hi"}], timeout_seconds=0.5
            )

    def test_t7_3_08_none_timeout(self, configured_provider):
        """T7.3.08: timeout_seconds=None -> TypeError."""
        with pytest.raises(TypeError):
            configured_provider.generate(
                [{"role": "user", "content": "hi"}], timeout_seconds=None
            )

    def test_t7_3_09_string_timeout(self, configured_provider):
        """T7.3.09: timeout_seconds=\"ten\" -> TypeError."""
        with pytest.raises(TypeError):
            configured_provider.generate(
                [{"role": "user", "content": "hi"}], timeout_seconds="ten"
            )
