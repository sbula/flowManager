"""Shared fixtures and mock provider for LLM Binding tests.

The MockProvider is a fully functional implementation of LLMProvider
that enforces the complete lifecycle contract from spec §3.

It is used as the test subject across all test files.
"""

import threading
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from flow.llm.errors import (
    LLMAuthError,
    LLMConnectionError,
    LLMGenerationError,
    ProviderAlreadyConfiguredError,
    ProviderConfigError,
    ProviderNotConfiguredError,
)
from flow.llm.factory import LLMFactory
from flow.llm.provider import LLMProvider


class MockProvider(LLMProvider):
    """A fully spec-compliant mock LLM provider for testing.

    Enforces the complete lifecycle state machine:
    Uninitialized -> Configured -> (Active use) -> Closed

    Each method checks _configured and _closed flags exactly
    as the spec requires.
    """

    _PROVIDER_NAME = "mock"

    def __init__(self) -> None:
        self._configured = False
        self._closed = False
        self._configure_called = False
        self._config: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()
        # Mock SDK client for resource leak testing
        self._sdk_client: Optional[MagicMock] = None
        # Hooks for controlling behavior in tests
        self._generate_response = "mock response"
        self._embed_response: Optional[List[List[float]]] = None
        self._token_count = 5
        self._generate_side_effect = None
        self._embed_side_effect = None
        self._configure_side_effect = None
        self._close_side_effect = None
        self._embedding_dims: Optional[int] = 768

    @property
    def provider_name(self) -> str:
        return self._PROVIDER_NAME

    @property
    def embedding_dimensions(self) -> Optional[int]:
        return self._embedding_dims

    def _check_configured(self) -> None:
        """Check lifecycle precondition for operation methods."""
        if self._closed or not self._configured:
            raise ProviderNotConfiguredError(
                "Provider is not configured. Call configure() first."
            )

    def configure(self, config: Dict[str, Any]) -> None:
        with self._lock:
            if self._configure_called:
                raise ProviderAlreadyConfiguredError(
                    "configure() has already been called. "
                    "Obtain a fresh instance via Factory.reset() + "
                    "Factory.create()."
                )
            self._configure_called = True

            if self._configure_side_effect:
                # Simulate partial init then failure
                self._sdk_client = MagicMock(name="mock_sdk_client")
                try:
                    raise self._configure_side_effect
                except Exception:
                    # Resource cleanup per spec §3 Lifecycle #5a
                    if self._sdk_client is not None:
                        self._sdk_client.close()
                    raise

            # Check for required 'model' key
            if "model" not in config:
                raise ProviderConfigError("Missing required 'model' key in config.")

            if config.get("model") == "":
                raise ProviderConfigError("Empty model name. Specify a valid model.")

            # Simulate auth check
            auth = config.get("auth", {})
            auth_method = auth.get("method", "api_key")

            if auth_method == "api_key":
                import os

                env_key = auth.get("api_key_env", "MOCK_API_KEY")
                api_key = os.environ.get(env_key, "")
                if not api_key or not api_key.strip():
                    raise LLMAuthError(
                        f"API key not found. Set {env_key} environment "
                        "variable or configure auth.method=keyring."
                    )
                # Sanitize the key
                api_key = self._sanitize_credential(api_key)

            self._config = config
            self._sdk_client = MagicMock(name="mock_sdk_client")
            self._configured = True

    def _sanitize_credential(self, key: str) -> str:
        """Strip invisible/unwanted characters from credentials.
        Per spec §4.4 Credential Sanitization."""
        # Strip whitespace, newlines, CRLF
        key = key.strip()
        key = key.replace("\r\n", "").replace("\r", "").replace("\n", "")
        key = key.replace("\t", "")
        # Strip BOM
        key = key.replace("\xef\xbb\xbf", "").replace("\ufeff", "")
        # Strip zero-width spaces
        key = key.replace("\u200b", "")
        # Strip non-breaking space
        key = key.replace("\u00a0", "")
        # Strip em space
        key = key.replace("\u2003", "")
        return key

    def _validate_single_message(self, msg: Any, index: int) -> None:
        """Validate a single message dict."""
        if not isinstance(msg, dict):
            raise ValueError(
                f"messages[{index}] must be a dict, got {type(msg).__name__}."
            )
        if "role" not in msg:
            raise ValueError(f"messages[{index}] is missing required 'role' key.")
        if "content" not in msg:
            raise ValueError(f"messages[{index}] is missing required 'content' key.")
        role = msg["role"]
        content = msg["content"]
        if not isinstance(role, str):
            raise ValueError(
                f"messages[{index}]['role'] must be a string, got "
                f"{type(role).__name__}."
            )
        if role not in self._VALID_ROLES:
            raise ValueError(
                f"messages[{index}]['role'] is '{role}', must be one "
                f"of: {sorted(self._VALID_ROLES)}."
            )
        if not isinstance(content, str):
            raise ValueError(
                f"messages[{index}]['content'] must be a string, got "
                f"{type(content).__name__}."
            )
        if content == "":
            raise ValueError(f"messages[{index}]['content'] must not be empty.")

    def _validate_messages(self, messages: Any) -> None:
        """Validate messages input per spec §3 generate() input validation."""
        if messages is None:
            raise ValueError("messages must not be None.")
        if not isinstance(messages, list):
            raise TypeError(f"messages must be a list, got {type(messages).__name__}.")
        if len(messages) == 0:
            raise ValueError("messages list must not be empty.")
        for i, msg in enumerate(messages):
            self._validate_single_message(msg, i)

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        timeout_seconds: int = 120,
        **kwargs,
    ) -> str:
        self._check_configured()
        self._validate_messages(messages)

        # Validate timeout
        if timeout_seconds is None:
            raise TypeError("timeout_seconds must be an int, got None.")
        if not isinstance(timeout_seconds, int):
            raise TypeError(
                f"timeout_seconds must be an int, got "
                f"{type(timeout_seconds).__name__}."
            )
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must not be negative.")
        if timeout_seconds == 0:
            raise TimeoutError("Immediate timeout (timeout_seconds=0).")

        # Check for side effects (test hooks)
        if self._generate_side_effect:
            raise self._generate_side_effect

        response = self._generate_response
        # Guard against None/empty per spec
        if response is None or not isinstance(response, str):
            raise LLMGenerationError("Provider returned None or non-string response.")
        if not response.strip():
            raise LLMGenerationError(
                "Provider returned empty or whitespace-only response."
            )
        return response

    def _validate_embed_input(self, texts: Any) -> None:
        """Validate embed input texts."""
        if texts is None:
            raise TypeError("texts must be a list, got None.")
        if not isinstance(texts, list):
            raise TypeError(f"texts must be a list, got {type(texts).__name__}.")
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise ValueError(
                    f"texts[{i}] must be a string, got {type(text).__name__}."
                )
            if text == "":
                raise ValueError(f"texts[{i}] must not be empty.")

    def embed(
        self,
        texts: List[str],
        *,
        timeout_seconds: int = 60,
    ) -> List[List[float]]:
        self._check_configured()
        self._validate_embed_input(texts)
        if len(texts) == 0:
            return []

        if self._embed_side_effect:
            raise self._embed_side_effect

        if self._embed_response is not None:
            return self._embed_response

        dim = self._embedding_dims or 768
        return [[0.1] * dim for _ in texts]

    def count_tokens(self, text: str) -> int:
        self._check_configured()
        if not isinstance(text, str):
            raise TypeError(f"text must be a string, got {type(text).__name__}.")
        if text == "":
            return 0
        return self._token_count

    def close(self) -> None:
        if self._close_side_effect and not self._closed:
            raise self._close_side_effect
        if self._sdk_client is not None:
            self._sdk_client.close()
        self._closed = True
        self._configured = False


class MockProviderBadName(MockProvider):
    """A mock provider that lies about its name (for registry tests)."""

    @property
    def provider_name(self) -> str:
        return "wrong_name"


class MockProviderNoEmbed(MockProvider):
    """A mock provider that doesn't support embeddings (like Anthropic)."""

    _PROVIDER_NAME = "mock_no_embed"

    def embed(self, texts, *, timeout_seconds=60):
        self._check_configured()
        raise NotImplementedError("This provider does not support embeddings.")


class MockProviderValidateOverride(MockProvider):
    """A mock provider that overrides validate() with a lightweight check."""

    def validate(self) -> bool:
        self._check_configured()
        return True


class MockProviderValidateError(MockProvider):
    """A mock provider whose validate() raises an exception."""

    def validate(self) -> bool:
        self._check_configured()
        raise LLMConnectionError("Cannot reach provider.")


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def raw_provider():
    """Returns a fresh, unconfigured MockProvider."""
    return MockProvider()


@pytest.fixture
def configured_provider(monkeypatch):
    """Returns a MockProvider that has been successfully configured."""
    monkeypatch.setenv("MOCK_API_KEY", "test-key-12345")
    p = MockProvider()
    p.configure({"model": "test-model", "auth": {"method": "api_key"}})
    return p


@pytest.fixture
def valid_messages():
    """Returns a valid messages list for generate()."""
    return [{"role": "user", "content": "Hello, world!"}]


@pytest.fixture
def factory_config():
    """Returns a minimal valid factory config with mock profiles."""
    return {
        "default": {
            "provider": "mock",
            "config": {"model": "test-model"},
            "auth": {"method": "none"},
        },
        "coding_expert": {
            "provider": "mock",
            "config": {"model": "expert-model"},
            "auth": {"method": "none"},
        },
    }


@pytest.fixture
def factory_with_mock(factory_config, monkeypatch):
    """Returns an LLMFactory pre-configured with mock provider registry.

    Patches the PROVIDER_REGISTRY to use MockProvider so tests don't
    need real SDKs.
    """
    import flow.llm.factory as factory_module

    original_registry = factory_module.PROVIDER_REGISTRY.copy()
    test_module = "tests.unit.llm.conftest"
    factory_module.PROVIDER_REGISTRY["mock"] = f"{test_module}.MockProvider"
    monkeypatch.setenv("MOCK_API_KEY", "test-key-12345")

    factory = LLMFactory(config=factory_config)
    yield factory

    # Restore original registry
    factory_module.PROVIDER_REGISTRY.clear()
    factory_module.PROVIDER_REGISTRY.update(original_registry)
