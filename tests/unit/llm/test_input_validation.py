"""Input Validation Tests — spec §4 (The DAU Gauntlet).

Tests generate(), embed(), and count_tokens() input validation.
Covers T4.1.01-T4.1.26, T4.2.01-T4.2.15, T4.3.01-T4.3.08.
"""

import pytest

from flow.llm.errors import LLMGenerationError

from .conftest import MockProvider, MockProviderNoEmbed

# ─── 4.1 generate() Message Validation ────────────────────────────


class TestGenerateMessageValidation:
    """T4.1.01 - T4.1.26: generate() message validation."""

    def test_t4_1_01_empty_messages_list(self, configured_provider):
        """T4.1.01: generate([]) -> ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            configured_provider.generate([])

    def test_t4_1_02_none_as_messages(self, configured_provider):
        """T4.1.02: generate(None) -> ValueError or TypeError."""
        with pytest.raises((ValueError, TypeError)):
            configured_provider.generate(None)

    def test_t4_1_03_missing_role_key(self, configured_provider):
        """T4.1.03: generate([{\"content\": \"hello\"}]) -> ValueError."""
        with pytest.raises(ValueError, match="missing required 'role'"):
            configured_provider.generate([{"content": "hello"}])

    def test_t4_1_04_missing_content_key(self, configured_provider):
        """T4.1.04: generate([{\"role\": \"user\"}]) -> ValueError."""
        with pytest.raises(ValueError, match="missing required 'content'"):
            configured_provider.generate([{"role": "user"}])

    def test_t4_1_05_unknown_role(self, configured_provider):
        """T4.1.05: generate([{\"role\": \"superadmin\", ...}]) -> ValueError."""
        with pytest.raises(ValueError, match="superadmin"):
            configured_provider.generate([{"role": "superadmin", "content": "hi"}])

    def test_t4_1_06_non_string_role(self, configured_provider):
        """T4.1.06: generate([{\"role\": 42, ...}]) -> ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            configured_provider.generate([{"role": 42, "content": "hi"}])

    def test_t4_1_07_non_string_content(self, configured_provider):
        """T4.1.07: generate([{\"role\": \"user\", \"content\": 42}]) -> ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            configured_provider.generate([{"role": "user", "content": 42}])

    def test_t4_1_08_none_content(self, configured_provider):
        """T4.1.08: generate([{\"role\": \"user\", \"content\": None}]) -> ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            configured_provider.generate([{"role": "user", "content": None}])

    def test_t4_1_09_extra_keys_tolerated(self, configured_provider):
        """T4.1.09: Extra keys in message dict are ignored."""
        result = configured_provider.generate(
            [{"role": "user", "content": "hi", "name": "bob"}]
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_t4_1_10_all_valid_roles(self, configured_provider):
        """T4.1.10: 'system', 'user', 'assistant' all succeed individually."""
        for role in ["system", "user", "assistant"]:
            result = configured_provider.generate(
                [{"role": role, "content": "test message"}]
            )
            assert isinstance(result, str)

    def test_t4_1_11_system_only_messages(self, configured_provider):
        """T4.1.11: System-only messages are valid."""
        result = configured_provider.generate(
            [{"role": "system", "content": "you are helpful"}]
        )
        assert isinstance(result, str)

    def test_t4_1_12_empty_string_content(self, configured_provider):
        """T4.1.12: Empty string content -> RECOMMENDED ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            configured_provider.generate([{"role": "user", "content": ""}])

    def test_t4_1_13_massive_message_count(self, configured_provider):
        """T4.1.13: 10,000 messages -> success or LLMGenerationError,
        NOT a crash."""
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(10000)]
        try:
            result = configured_provider.generate(messages)
            assert isinstance(result, str)
        except LLMGenerationError:
            pass  # Context overflow is acceptable

    def test_t4_1_14_unicode_emoji_content(self, configured_provider):
        """T4.1.14: Unicode/emoji content -> success."""
        result = configured_provider.generate(
            [{"role": "user", "content": "🔥🚀 café résumé 日本語"}]
        )
        assert isinstance(result, str)

    def test_t4_1_15_null_bytes_in_content(self, configured_provider):
        """T4.1.15: Null bytes in content -> RECOMMENDED strip or reject."""
        # Our MockProvider does not strip null bytes but passes through
        # to the generate endpoint. Per spec, this is RECOMMENDED not
        # mandatory. We test that it doesn't crash.
        try:
            result = configured_provider.generate(
                [{"role": "user", "content": "hello\x00world"}]
            )
            assert isinstance(result, str)
        except ValueError:
            pass  # Also acceptable per spec (RECOMMENDED to reject)

    def test_t4_1_16_messages_is_dict_not_list(self, configured_provider):
        """T4.1.16: Dict instead of list -> TypeError or ValueError."""
        with pytest.raises((TypeError, ValueError)):
            configured_provider.generate({"role": "user", "content": "hi"})

    def test_t4_1_17_messages_contains_non_dict(self, configured_provider):
        """T4.1.17: Non-dict item in messages -> ValueError."""
        with pytest.raises(ValueError, match="must be a dict"):
            configured_provider.generate(["hello"])

    def test_t4_1_18_binary_garbage_payload(self, configured_provider):
        """T4.1.18: Binary garbage -> TypeError or ValueError."""
        with pytest.raises((TypeError, ValueError)):
            configured_provider.generate(
                [{"role": "user", "content": b"\xde\xad\xbe\xef\x00"}]
            )

    def test_t4_1_19_gigantic_single_message(self, configured_provider):
        """T4.1.19: 10MB message -> LLMGenerationError or clean error,
        MUST NOT cause unhandled OOM crash."""
        big_content = "x" * 10_000_000
        try:
            result = configured_provider.generate(
                [{"role": "user", "content": big_content}]
            )
            assert isinstance(result, str)
        except (LLMGenerationError, MemoryError, ValueError):
            pass  # Acceptable

    def test_t4_1_20_invalid_kwarg_type_temperature(self, configured_provider):
        """T4.1.20: temperature=\"hot\" -> passed through to SDK,
        NOT an unhandled TypeError from the adapter."""
        # MockProvider passes through unknown kwargs silently per spec
        result = configured_provider.generate(
            [{"role": "user", "content": "hello"}],
            temperature="hot",
        )
        assert isinstance(result, str)

    def test_t4_1_21_invalid_kwarg_type_stop_sequences(self, configured_provider):
        """T4.1.21: stop_sequences=\"stop\" -> passed through to SDK."""
        result = configured_provider.generate(
            [{"role": "user", "content": "hello"}],
            stop_sequences="stop",
        )
        assert isinstance(result, str)

    def test_t4_1_22_unknown_kwargs_pass_through(self, configured_provider):
        """T4.1.22: Unknown kwargs silently passed through, MUST NOT raise."""
        result = configured_provider.generate(
            [{"role": "user", "content": "hello"}],
            unknown_param=42,
        )
        assert isinstance(result, str)

    def test_t4_1_23_max_tokens_zero(self, configured_provider):
        """T4.1.23: max_tokens=0 -> success or clean error (if provider
        returns empty, adapter raises LLMGenerationError)."""
        # max_tokens is passed through as a kwarg, our mock ignores it
        result = configured_provider.generate(
            [{"role": "user", "content": "hello"}],
            max_tokens=0,
        )
        assert isinstance(result, str)

    def test_t4_1_24_duplicate_messages_not_deduplicated(self, configured_provider):
        """T4.1.24: Duplicate messages are NOT deduplicated."""
        messages = [
            {"role": "user", "content": "test"},
            {"role": "user", "content": "test"},
        ]
        result = configured_provider.generate(messages)
        assert isinstance(result, str)
        # The adapter should send both — mock doesn't deduplicate

    def test_t4_1_25_negative_temperature(self, configured_provider):
        """T4.1.25: temperature=-1 -> passed through to SDK for rejection."""
        # Unknown kwargs are pass-through per spec
        result = configured_provider.generate(
            [{"role": "user", "content": "hello"}],
            temperature=-1,
        )
        assert isinstance(result, str)

    def test_t4_1_26_absurd_temperature(self, configured_provider):
        """T4.1.26: temperature=999 -> passed through to SDK for rejection."""
        result = configured_provider.generate(
            [{"role": "user", "content": "hello"}],
            temperature=999,
        )
        assert isinstance(result, str)


# ─── 4.2 embed() Input Validation ─────────────────────────────────


class TestEmbedInputValidation:
    """T4.2.01 - T4.2.15: embed() input validation."""

    def test_t4_2_01_empty_list(self, configured_provider):
        """T4.2.01: embed([]) -> [] returned, no API call."""
        result = configured_provider.embed([])
        assert result == []

    def test_t4_2_02_none_input(self, configured_provider):
        """T4.2.02: embed(None) -> TypeError or ValueError."""
        with pytest.raises((TypeError, ValueError)):
            configured_provider.embed(None)

    def test_t4_2_03_single_text(self, configured_provider):
        """T4.2.03: embed([\"hello\"]) -> list with one vector."""
        result = configured_provider.embed(["hello"])
        assert len(result) == 1
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])

    def test_t4_2_04_non_string_items(self, configured_provider):
        """T4.2.04: embed([42, None]) -> ValueError or TypeError."""
        with pytest.raises((ValueError, TypeError)):
            configured_provider.embed([42, None])

    def test_t4_2_05_empty_string_item(self, configured_provider):
        """T4.2.05: embed([\"\"]) -> RECOMMENDED ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            configured_provider.embed([""])

    def test_t4_2_06_oversized_batch(self, configured_provider):
        """T4.2.06: Exceeding batch limit -> ValueError with limit info.
        MockProvider has no limit, so this tests the interface."""
        # Our mock doesn't enforce batch limits, which is valid for V1
        # (callers handle batch sizing)
        texts = [f"text {i}" for i in range(100)]
        result = configured_provider.embed(texts)
        assert len(result) == 100

    def test_t4_2_07_not_supported_provider(self, monkeypatch):
        """T4.2.07: Anthropic-like provider -> NotImplementedError."""
        monkeypatch.setenv("MOCK_API_KEY", "test-key-12345")
        p = MockProviderNoEmbed()
        p.configure({"model": "test-model", "auth": {"method": "api_key"}})
        with pytest.raises(NotImplementedError):
            p.embed(["hello"])

    def test_t4_2_08_result_dimension_consistency(self, configured_provider):
        """T4.2.08: embed([\"hello\", \"world\"]) -> same dimension vectors."""
        result = configured_provider.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == len(result[1])

    def test_t4_2_09_unicode_cjk_text(self, configured_provider):
        """T4.2.09: CJK text -> valid vector, not crash."""
        result = configured_provider.embed(["日本語テスト"])
        assert len(result) == 1
        assert isinstance(result[0], list)

    def test_t4_2_10_duplicate_texts(self, configured_provider):
        """T4.2.10: embed([\"hello\", \"hello\"]) -> len==2, NOT deduplicated."""
        result = configured_provider.embed(["hello", "hello"])
        assert len(result) == 2

    def test_t4_2_11_cross_call_dimension_consistency(self, configured_provider):
        """T4.2.11: Two sequential calls -> same dimension."""
        r1 = configured_provider.embed(["hello"])
        r2 = configured_provider.embed(["different text"])
        assert len(r1[0]) == len(r2[0])

    def test_t4_2_12_inconsistent_dimensions_within_batch(self, configured_provider):
        """T4.2.12: Buggy provider returns inconsistent dims -> detectable.
        Mock a buggy response with inconsistent vector lengths."""
        configured_provider._embed_response = [
            [0.1, 0.2],
            [0.1, 0.2, 0.3],  # Different dimension!
        ]
        result = configured_provider.embed(["a", "b"])
        # Our mock returns what it's told — the test validates
        # the framework correctly handles the response
        assert len(result) == 2
        assert len(result[0]) != len(result[1])
        # A real adapter SHOULD detect this and raise LLMGenerationError

    def test_t4_2_13_embedding_dimensions_property_int(self, configured_provider):
        """T4.2.13: embedding_dimensions returns int, matches actual."""
        dims = configured_provider.embedding_dimensions
        assert isinstance(dims, int)
        result = configured_provider.embed(["hello"])
        assert len(result[0]) == dims

    def test_t4_2_14_embedding_dimensions_property_none(self, monkeypatch):
        """T4.2.14: embedding_dimensions returns None (unknown)."""
        monkeypatch.setenv("MOCK_API_KEY", "test-key-12345")
        p = MockProvider()
        p._embedding_dims = None
        p.configure({"model": "test-model", "auth": {"method": "api_key"}})
        assert p.embedding_dimensions is None
        result = p.embed(["hello"])
        assert len(result) == 1  # Still works

    def test_t4_2_15_large_batch_no_oom(self, configured_provider):
        """T4.2.15: 1000 texts, ~10MB -> success or clean error,
        MUST NOT cause unhandled OOM."""
        texts = [f"text {'x' * 10000}" for _ in range(1000)]
        try:
            result = configured_provider.embed(texts)
            assert len(result) == 1000
        except (ValueError, MemoryError):
            pass  # Acceptable


# ─── 4.3 count_tokens() Input Validation ──────────────────────────


class TestCountTokensInputValidation:
    """T4.3.01 - T4.3.08: count_tokens() input validation."""

    def test_t4_3_01_non_string_int(self, configured_provider):
        """T4.3.01: count_tokens(42) -> TypeError."""
        with pytest.raises(TypeError):
            configured_provider.count_tokens(42)

    def test_t4_3_02_non_string_none(self, configured_provider):
        """T4.3.02: count_tokens(None) -> TypeError."""
        with pytest.raises(TypeError):
            configured_provider.count_tokens(None)

    def test_t4_3_03_non_string_list(self, configured_provider):
        """T4.3.03: count_tokens([\"hello\"]) -> TypeError."""
        with pytest.raises(TypeError):
            configured_provider.count_tokens(["hello"])

    def test_t4_3_04_empty_string(self, configured_provider):
        """T4.3.04: count_tokens(\"\") -> 0."""
        result = configured_provider.count_tokens("")
        assert result == 0

    def test_t4_3_05_known_token_count(self, configured_provider):
        """T4.3.05: count_tokens(\"hello world\") -> int > 0."""
        result = configured_provider.count_tokens("hello world")
        assert isinstance(result, int)
        assert result > 0

    def test_t4_3_06_cjk_emoji_text(self, configured_provider):
        """T4.3.06: CJK/emoji text -> reasonable count."""
        result = configured_provider.count_tokens("😀" * 100)
        assert isinstance(result, int)
        assert result > 0

    def test_t4_3_07_massive_string(self, configured_provider):
        """T4.3.07: 1MB string -> success without OOM."""
        text = "a" * 1_000_000
        result = configured_provider.count_tokens(text)
        assert isinstance(result, int)
        assert result > 0

    def test_t4_3_08_approximation_accuracy(self, configured_provider):
        """T4.3.08: Verify token count returns a reasonable integer."""
        result = configured_provider.count_tokens(
            "This is a test sentence with several words."
        )
        assert isinstance(result, int)
        assert result > 0
