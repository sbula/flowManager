"""Anthropic (Claude) LLM Provider Adapter.

Implements LLMProvider ABC for Anthropic Claude models.
See 01_06_llm_binding_spec.md §3–§6 for full specification.

Dependency: anthropic (optional, installed via `poetry install -E anthropic`)
"""

import logging
import os
import threading
from typing import Any, Dict, List, Optional

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

# Deferred import — MissingDependencyError raised in configure() if absent
try:
    import anthropic as anthropic_sdk
except ImportError:
    anthropic_sdk = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude adapter (API Key, Keyring).

    Thread-safe. No mutable state beyond SDK client handle.
    Anthropic does NOT support embeddings — embed() raises NotImplementedError.
    """

    _PROVIDER_NAME = "anthropic"

    def __init__(self) -> None:
        self._configured = False
        self._closed = False
        self._configure_called = False
        self._lock = threading.Lock()
        self._client: Any = None
        self._model: Optional[str] = None
        self._profile_name: Optional[str] = None
        self._max_tokens: int = 4096  # Anthropic requires max_tokens

    @property
    def provider_name(self) -> str:
        return self._PROVIDER_NAME

    @property
    def embedding_dimensions(self) -> Optional[int]:
        # Anthropic does not support embeddings
        return None

    def _check_configured(self) -> None:
        if self._closed or not self._configured:
            raise ProviderNotConfiguredError(
                "Provider is not configured. Call configure() first."
            )

    def _sanitize_credential(self, key: str) -> str:
        """Strip invisible/unwanted characters per spec §4.4."""
        key = key.strip()
        key = key.replace("\r\n", "").replace("\r", "").replace("\n", "")
        key = key.replace("\t", "")
        key = key.replace("\xef\xbb\xbf", "").replace("\ufeff", "")
        key = key.replace("\u200b", "")
        key = key.replace("\u00a0", "")
        key = key.replace("\u2003", "")
        return key

    def _validate_auth_method(self, auth: Dict) -> str:
        """Validate and return the auth method for Anthropic."""
        auth_method = auth.get("method", "api_key")
        if not auth_method:
            logger.warning("No auth method specified, defaulting to 'api_key'")
            return "api_key"
        if auth_method == "none":
            raise ProviderConfigError(
                "Anthropic requires authentication. method='none' is not supported."
            )
        if auth_method in ("adc", "vertex_adc"):
            raise ProviderConfigError(
                f"Auth method '{auth_method}' is not supported "
                "by Anthropic. Use 'api_key' or 'keyring'."
            )
        if auth_method not in ("api_key", "keyring"):
            raise ProviderConfigError(
                f"Unknown auth method '{auth_method}'. "
                "Supported for Anthropic: api_key, keyring."
            )
        return auth_method

    def _init_client(self, auth_method: str, auth: Dict) -> Any:
        """Initialize the SDK client with error-safe cleanup."""
        client = None
        try:
            if auth_method == "api_key":
                client = self._configure_api_key(auth)
            elif auth_method == "keyring":
                client = self._configure_keyring(auth)
        except (LLMAuthError, ProviderConfigError, MissingDependencyError):
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise
        except Exception as e:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise LLMAuthError(
                f"Failed to initialize Anthropic client: {type(e).__name__}"
            ) from e
        return client

    def configure(self, config: Dict[str, Any]) -> None:
        with self._lock:
            if self._configure_called:
                raise ProviderAlreadyConfiguredError(
                    "configure() has already been called. "
                    "Obtain a fresh instance via Factory.reset() + "
                    "Factory.create()."
                )
            self._configure_called = True

        if "model" not in config:
            raise ProviderConfigError("Missing required 'model' key in config.")
        model = config["model"]
        if isinstance(model, str) and model.strip() == "":
            raise ProviderConfigError("Empty model name. Specify a valid model.")

        auth = config.get("auth", {})
        auth_method = self._validate_auth_method(auth)

        if anthropic_sdk is None:
            raise MissingDependencyError(
                "Anthropic SDK not installed. "
                "Run 'pip install anthropic' or "
                "'poetry install -E anthropic'."
            )

        self._model = str(model)
        self._profile_name = config.get("profile_name", "unknown")
        self._max_tokens = config.get("max_tokens", 4096)

        self._client = self._init_client(auth_method, auth)
        self._configured = True

    def _configure_api_key(self, auth: Dict) -> Any:
        env_key = auth.get("api_key_env", "ANTHROPIC_API_KEY")
        api_key = os.environ.get(env_key, "")
        if not api_key or not api_key.strip():
            raise LLMAuthError(
                f"API key not found. Set {env_key} environment "
                "variable, run 'flow secret set ANTHROPIC_API_KEY', "
                "or configure auth.method=keyring in the profile."
            )
        api_key = self._sanitize_credential(api_key)
        return anthropic_sdk.Anthropic(api_key=api_key)

    def _configure_keyring(self, auth: Dict) -> Any:
        """Resolve from keyring with 3s timeout per spec §4.6."""
        import concurrent.futures

        env_key = auth.get("api_key_env", "ANTHROPIC_API_KEY")
        # Check env var first (env overrides keyring per §4.6.4)
        api_key = os.environ.get(env_key, "")
        if api_key and api_key.strip():
            return anthropic_sdk.Anthropic(api_key=self._sanitize_credential(api_key))

        try:
            import keyring as kr
        except ImportError:
            raise MissingDependencyError(
                "Run 'pip install keyring' to use OS keyring " "authentication."
            )

        service = auth.get("keyring_service", "flowmanager")
        key_name = auth.get("keyring_key", env_key)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(kr.get_password, service, key_name)
            try:
                api_key = future.result(timeout=3.0)
            except concurrent.futures.TimeoutError:
                raise LLMAuthError(
                    "OS Keyring locked or unresponsive in headless "
                    "environment. Set ANTHROPIC_API_KEY env var instead."
                )

        if not api_key:
            raise LLMAuthError(
                f"API key not found in keyring. "
                f"Run 'flow secret set {key_name}' to store it."
            )
        return anthropic_sdk.Anthropic(api_key=self._sanitize_credential(api_key))

    def _validate_single_message(self, i: int, msg: Any) -> None:
        """Validate a single message dict at index i."""
        if not isinstance(msg, dict):
            raise ValueError(
                f"messages[{i}] must be a dict, got {type(msg).__name__}."
            )
        if "role" not in msg:
            raise ValueError(f"messages[{i}] is missing required 'role' key.")
        if "content" not in msg:
            raise ValueError(f"messages[{i}] is missing required 'content' key.")
        role = msg["role"]
        content = msg["content"]
        if not isinstance(role, str):
            raise ValueError(
                f"messages[{i}]['role'] must be a string, got "
                f"{type(role).__name__}."
            )
        if role not in self._VALID_ROLES:
            raise ValueError(
                f"messages[{i}]['role'] is '{role}', must be one "
                f"of: {sorted(self._VALID_ROLES)}."
            )
        if not isinstance(content, str):
            raise ValueError(
                f"messages[{i}]['content'] must be a string, got "
                f"{type(content).__name__}."
            )
        if content == "":
            raise ValueError(f"messages[{i}]['content'] must not be empty.")

    def _validate_messages(self, messages: Any) -> None:
        """Validate messages input per spec §3."""
        if messages is None:
            raise ValueError("messages must not be None.")
        if not isinstance(messages, list):
            raise TypeError(f"messages must be a list, got {type(messages).__name__}.")
        if len(messages) == 0:
            raise ValueError("messages list must not be empty.")
        for i, msg in enumerate(messages):
            self._validate_single_message(i, msg)

    @staticmethod
    def _validate_timeout(timeout_seconds: Any) -> None:
        """Validate timeout_seconds parameter."""
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

    @staticmethod
    def _prepare_api_messages(messages: List[Dict[str, str]]):
        """Separate system message from user/assistant messages."""
        system_text = None
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})
        if not api_messages:
            api_messages = [{"role": "user", "content": system_text or "."}]
            system_text = None
        return system_text, api_messages

    def _extract_generate_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and validate standardized kwargs for create()."""
        create_kwargs: Dict[str, Any] = {}
        create_kwargs["max_tokens"] = kwargs.pop("max_tokens", self._max_tokens)
        if "temperature" in kwargs:
            temp = kwargs.pop("temperature")
            if not isinstance(temp, (int, float)):
                raise ValueError(
                    f"temperature must be a number, got {type(temp).__name__}."
                )
            if temp < 0:
                raise ValueError("temperature must not be negative.")
            create_kwargs["temperature"] = temp
        if "stop_sequences" in kwargs:
            stop = kwargs.pop("stop_sequences")
            if not isinstance(stop, list):
                raise ValueError("stop_sequences must be a list of strings.")
            create_kwargs["stop_sequences"] = stop
        if "top_p" in kwargs:
            create_kwargs["top_p"] = kwargs.pop("top_p")
        if "top_k" in kwargs:
            create_kwargs["top_k"] = kwargs.pop("top_k")
        return create_kwargs

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """Extract text from Anthropic SDK response."""
        text = None
        try:
            if hasattr(response, "content") and response.content:
                text_blocks = [
                    block.text for block in response.content if hasattr(block, "text")
                ]
                text = "".join(text_blocks)
        except (AttributeError, TypeError) as e:
            raise LLMGenerationError(
                "Malformed SDK response: cannot extract text. "
                f"{type(e).__name__}: {e}"
            ) from e
        if text is None:
            raise LLMGenerationError("Provider returned None response.")
        if not text.strip():
            raise LLMGenerationError(
                "Provider returned empty or whitespace-only response."
            )
        return text

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        timeout_seconds: int = 120,
        **kwargs: Any,
    ) -> str:
        self._check_configured()
        self._validate_messages(messages)
        self._validate_timeout(timeout_seconds)

        system_text, api_messages = self._prepare_api_messages(messages)
        create_kwargs = self._extract_generate_kwargs(kwargs)

        import time

        start = time.time()
        try:
            response = self._client.messages.create(
                model=self._model,
                messages=api_messages,
                system=system_text if system_text else anthropic_sdk.NOT_GIVEN,
                timeout=float(timeout_seconds),
                **create_kwargs,
            )
            latency_ms = int((time.time() - start) * 1000)
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self._map_sdk_error(e, latency_ms)
            raise  # unreachable

        text = self._extract_response_text(response)

        logger.info(
            "generate() completed",
            extra={
                "profile_name": self._profile_name,
                "model": self._model,
                "latency_ms": latency_ms,
                "status": "success",
                "prompt_tokens": getattr(
                    getattr(response, "usage", None),
                    "input_tokens",
                    None,
                ),
                "completion_tokens": getattr(
                    getattr(response, "usage", None),
                    "output_tokens",
                    None,
                ),
            },
        )
        return text

    def _map_sdk_typed_error(self, error: Exception, error_type: str) -> None:
        """Map Anthropic SDK typed exceptions. Raises on match."""
        if anthropic_sdk is None:
            return
        if isinstance(error, anthropic_sdk.AuthenticationError):
            raise LLMAuthError(f"Authentication failed: {error_type}") from error
        if isinstance(error, anthropic_sdk.PermissionDeniedError):
            raise LLMAuthError(f"Permission denied: {error_type}") from error
        if isinstance(error, anthropic_sdk.RateLimitError):
            raise LLMRateLimitError(f"Rate limit exceeded: {error_type}") from error
        if isinstance(error, anthropic_sdk.NotFoundError):
            raise ProviderConfigError(
                f"Model '{self._model}' not found. "
                f"Update the profile config. ({error_type})"
            ) from error
        if isinstance(
            error,
            (anthropic_sdk.APIConnectionError, anthropic_sdk.InternalServerError),
        ):
            raise LLMConnectionError(f"Connection error: {error_type}") from error
        if isinstance(error, anthropic_sdk.APIStatusError):
            self._map_api_status_error(error, error_type)

    def _map_api_status_error(self, error: Exception, error_type: str) -> None:
        """Map APIStatusError by HTTP status code."""
        status = getattr(error, "status_code", 0)
        if status in (401, 403):
            raise LLMAuthError(f"Auth error (HTTP {status}): {error_type}") from error
        if status == 429:
            raise LLMRateLimitError(f"Rate limit (HTTP 429): {error_type}") from error
        if status == 404:
            raise ProviderConfigError(
                f"Model '{self._model}' not found (HTTP 404)"
            ) from error
        if status in (500, 502, 503, 504):
            raise LLMConnectionError(
                f"Server error (HTTP {status}): {error_type}"
            ) from error

    @staticmethod
    def _map_heuristic_error(error: Exception, error_str: str, error_type: str) -> None:
        """Fallback heuristic error mapping by string matching."""
        _MATCHERS = [
            (lambda s: "401" in s or "403" in s,
             lambda: LLMAuthError(f"Authentication failed: {error_type}")),
            (lambda s: "429" in s or "rate" in s,
             lambda: LLMRateLimitError(f"Rate limit exceeded: {error_type}")),
            (lambda s: "ssl" in s or "certificate" in s,
             lambda: LLMConnectionError(f"SSL/Certificate error: {error_type}")),
            (lambda s: "connection" in s or "timeout" in s,
             lambda: LLMConnectionError(f"Connection error: {error_type}")),
            (lambda s: "context" in s and "window" in s,
             lambda: LLMGenerationError(f"Context window overflow: {error_type}")),
        ]
        for predicate, exc_factory in _MATCHERS:
            if predicate(error_str):
                raise exc_factory() from error
        raise LLMGenerationError(f"Generation failed: {error_type}: {error}") from error

    def _map_sdk_error(self, error: Exception, latency_ms: int) -> None:
        """Map SDK exceptions to standard error hierarchy per §6.2."""
        error_str = str(error).lower()
        error_type = type(error).__name__

        logger.error(
            "generate() failed",
            extra={
                "profile_name": self._profile_name,
                "model": self._model,
                "latency_ms": latency_ms,
                "status": "error",
                "error_type": error_type,
            },
        )

        self._map_sdk_typed_error(error, error_type)
        self._map_heuristic_error(error, error_str, error_type)

    def embed(
        self,
        texts: List[str],
        *,
        timeout_seconds: int = 60,
    ) -> List[List[float]]:
        self._check_configured()
        raise NotImplementedError(
            "Anthropic does not support embeddings. "
            "Use a provider with embedding support (e.g., Gemini, "
            "OpenAI) for RAG workflows."
        )

    def count_tokens(self, text: str) -> int:
        self._check_configured()
        if not isinstance(text, str):
            raise TypeError(f"text must be a string, got {type(text).__name__}.")
        if text == "":
            return 0

        # Anthropic SDK has count_tokens method
        try:
            result = self._client.count_tokens(
                model=self._model,
                messages=[{"role": "user", "content": text}],
            )
            return result.input_tokens
        except Exception:
            # Fallback: approximation
            logger.warning(
                "Native token counting failed for Anthropic, "
                "using approximation (chars/4)."
            )
            return max(1, len(text) // 4)

    def validate(self) -> bool:
        """Lightweight check — verify client connectivity."""
        self._check_configured()
        try:
            # Use a minimal API call to verify connectivity
            # Anthropic doesn't have a models.list(), so we use
            # a count_tokens call which is very cheap
            self._client.count_tokens(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._closed = True
        self._configured = False
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
