"""Gemini LLM Provider Adapter.

Implements LLMProvider ABC for Google Gemini (API Key, ADC, Vertex AI).
See 01_06_llm_binding_spec.md §3–§6 for full specification.

Dependency: google-genai (optional, installed via `poetry install -E google`)
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
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini adapter (API Key, ADC, Vertex AI).

    Thread-safe. No mutable state beyond SDK client handle.
    """

    _PROVIDER_NAME = "gemini"
    _DEFAULT_EMBEDDING_MODEL = "text-embedding-004"
    _EMBEDDING_DIMS = 768

    def __init__(self) -> None:
        self._configured = False
        self._closed = False
        self._configure_called = False
        self._lock = threading.Lock()
        self._client: Any = None
        self._model: Optional[str] = None
        self._embedding_model: Optional[str] = None
        self._profile_name: Optional[str] = None

    @property
    def provider_name(self) -> str:
        return self._PROVIDER_NAME

    @property
    def embedding_dimensions(self) -> Optional[int]:
        return self._EMBEDDING_DIMS if self._configured else None

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

    def configure(self, config: Dict[str, Any]) -> None:
        with self._lock:
            if self._configure_called:
                raise ProviderAlreadyConfiguredError(
                    "configure() has already been called. "
                    "Obtain a fresh instance via Factory.reset() + "
                    "Factory.create()."
                )
            self._configure_called = True

        # Validate model FIRST (structural config — needs no SDK)
        if "model" not in config:
            raise ProviderConfigError("Missing required 'model' key in config.")
        model = config["model"]
        if isinstance(model, str) and model.strip() == "":
            raise ProviderConfigError("Empty model name. Specify a valid model.")

        if genai is None:
            raise MissingDependencyError(
                "Google Gemini SDK not installed. "
                "Run 'pip install google-genai' or "
                "'poetry install -E google'."
            )

        self._model = str(model)
        self._embedding_model = config.get(
            "embedding_model", self._DEFAULT_EMBEDDING_MODEL
        )
        self._profile_name = config.get("profile_name", "unknown")

        # Auth resolution
        auth = config.get("auth", {})
        auth_method = auth.get("method", "api_key")

        if not auth_method:
            auth_method = "api_key"
            logger.warning("No auth method specified, defaulting to 'api_key'")

        client = None
        try:
            if auth_method == "api_key":
                client = self._configure_api_key(auth)
            elif auth_method == "adc":
                client = self._configure_adc()
            elif auth_method == "vertex_adc":
                client = self._configure_vertex_adc(auth)
            elif auth_method == "keyring":
                client = self._configure_keyring(auth)
            elif auth_method == "none":
                # Local Gemini instance (unusual but possible)
                client = genai.Client(api_key="dummy")
            else:
                raise ProviderConfigError(
                    f"Unknown auth method '{auth_method}'. "
                    "Supported: api_key, adc, vertex_adc, keyring, none."
                )
        except (LLMAuthError, ProviderConfigError, MissingDependencyError):
            # Clean up partial init
            if client is not None:
                try:
                    # genai.Client doesn't have a close(), but guard anyway
                    if hasattr(client, "close"):
                        client.close()
                except Exception:
                    pass
            raise
        except Exception as e:
            if client is not None:
                try:
                    if hasattr(client, "close"):
                        client.close()
                except Exception:
                    pass
            raise LLMAuthError(
                f"Failed to initialize Gemini client: {type(e).__name__}"
            ) from e

        self._client = client
        self._configured = True

    def _configure_api_key(self, auth: Dict) -> Any:
        env_key = auth.get("api_key_env", "GOOGLE_API_KEY")
        api_key = os.environ.get(env_key, "")
        if not api_key or not api_key.strip():
            raise LLMAuthError(
                f"API key not found. Set {env_key} environment "
                "variable, run 'flow secret set GOOGLE_API_KEY', "
                "or configure auth.method=adc for SSO."
            )
        api_key = self._sanitize_credential(api_key)
        return genai.Client(api_key=api_key)

    def _configure_adc(self) -> Any:
        """Configure using Application Default Credentials."""
        try:
            return genai.Client()
        except Exception as e:
            raise LLMAuthError(
                "Google ADC token expired or revoked. "
                "Run 'gcloud auth application-default login' "
                "to re-authenticate."
            ) from e

    def _configure_vertex_adc(self, auth: Dict) -> Any:
        project_id = auth.get("project_id")
        location = auth.get("location")
        if not project_id:
            raise ProviderConfigError("Vertex AI requires 'project_id' in auth config.")
        if not location:
            location = "us-central1"
        try:
            return genai.Client(vertexai=True, project=project_id, location=location)
        except Exception as e:
            raise LLMAuthError(
                f"Vertex AI ADC initialization failed: {type(e).__name__}"
            ) from e

    def _configure_keyring(self, auth: Dict) -> Any:
        """Resolve from keyring with 3s timeout per spec §4.6."""
        import concurrent.futures

        env_key = auth.get("api_key_env", "GOOGLE_API_KEY")
        # Check env var first (env overrides keyring per §4.6.4)
        api_key = os.environ.get(env_key, "")
        if api_key and api_key.strip():
            return genai.Client(api_key=self._sanitize_credential(api_key))

        try:
            import keyring as kr
        except ImportError:
            raise MissingDependencyError(
                "Run 'pip install keyring' to use OS keyring " "authentication."
            )

        service = auth.get("keyring_service", "flowmanager")
        key_name = auth.get("keyring_key", env_key)

        # 3s hard timeout for keyring
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(kr.get_password, service, key_name)
            try:
                api_key = future.result(timeout=3.0)
            except concurrent.futures.TimeoutError:
                raise LLMAuthError(
                    "OS Keyring locked or unresponsive in headless "
                    "environment. Set GOOGLE_API_KEY env var instead."
                )

        if not api_key:
            raise LLMAuthError(
                f"API key not found in keyring. "
                f"Run 'flow secret set {key_name}' to store it."
            )
        return genai.Client(api_key=self._sanitize_credential(api_key))

    def _validate_messages(self, messages: Any) -> None:
        """Validate messages input per spec §3."""
        if messages is None:
            raise ValueError("messages must not be None.")
        if not isinstance(messages, list):
            raise TypeError(f"messages must be a list, got {type(messages).__name__}.")
        if len(messages) == 0:
            raise ValueError("messages list must not be empty.")
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise ValueError(
                    f"messages[{i}] must be a dict, got " f"{type(msg).__name__}."
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

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        timeout_seconds: int = 120,
        **kwargs: Any,
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

        # Build contents for Gemini SDK
        contents = self._messages_to_contents(messages)

        # Extract standardized kwargs
        gen_config = {}
        if "temperature" in kwargs:
            temp = kwargs.pop("temperature")
            if not isinstance(temp, (int, float)):
                raise ValueError(
                    f"temperature must be a number, got " f"{type(temp).__name__}."
                )
            if temp < 0:
                raise ValueError("temperature must not be negative.")
            gen_config["temperature"] = temp
        if "max_tokens" in kwargs:
            max_t = kwargs.pop("max_tokens")
            gen_config["max_output_tokens"] = max_t
        if "stop_sequences" in kwargs:
            stop = kwargs.pop("stop_sequences")
            if not isinstance(stop, list):
                raise ValueError("stop_sequences must be a list of strings.")
            gen_config["stop_sequences"] = stop
        if "top_p" in kwargs:
            gen_config["top_p"] = kwargs.pop("top_p")
        if "top_k" in kwargs:
            gen_config["top_k"] = kwargs.pop("top_k")

        # Pass-through remaining kwargs  (spec: unknown kwargs passed to SDK)
        # Gemini doesn't accept arbitrary kwargs, but we don't reject them
        _ = kwargs  # silently consumed

        import time

        start = time.time()
        try:
            config_obj = None
            if gen_config:
                config_obj = genai_types.GenerateContentConfig(**gen_config)
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=config_obj,
            )
            latency_ms = int((time.time() - start) * 1000)
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self._map_sdk_error(e, latency_ms)
            raise  # unreachable, _map_sdk_error always raises

        # Guard against None/empty per spec
        text = None
        try:
            text = response.text
        except (AttributeError, ValueError) as e:
            raise LLMGenerationError(
                "Malformed SDK response: cannot extract text. "
                f"{type(e).__name__}: {e}"
            ) from e

        if text is None:
            raise LLMGenerationError(
                "Provider returned None response (possible safety "
                "filter). Check content policy."
            )
        if not text.strip():
            raise LLMGenerationError(
                "Provider returned empty or whitespace-only response."
            )

        logger.info(
            "generate() completed",
            extra={
                "profile_name": self._profile_name,
                "model": self._model,
                "latency_ms": latency_ms,
                "status": "success",
            },
        )
        return text

    def _messages_to_contents(self, messages: List[Dict[str, str]]) -> Any:
        """Convert standard messages format to Gemini contents."""
        contents = []
        system_instruction = None
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_instruction = content
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append(
                    genai_types.Content(
                        role=gemini_role,
                        parts=[genai_types.Part(text=content)],
                    )
                )
        if not contents:
            # system-only: create a user message from system content
            contents.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=system_instruction or ".")],
                )
            )
        return contents

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

        # Auth errors
        if "401" in error_str or "403" in error_str or "api key" in error_str:
            raise LLMAuthError(f"Authentication failed: {error_type}") from error

        # Rate limit
        if "429" in error_str or "rate" in error_str or "quota" in error_str:
            raise LLMRateLimitError(f"Rate limit exceeded: {error_type}") from error

        # Model not found
        if "404" in error_str or "not found" in error_str:
            raise ProviderConfigError(
                f"Model '{self._model}' not found or deprecated. "
                f"Update the profile config. ({error_type})"
            ) from error

        # Connection / network
        if any(
            kw in error_str
            for kw in [
                "connection",
                "network",
                "dns",
                "ssl",
                "timeout",
                "certificate",
                "502",
                "504",
                "jsondecodeerror",
            ]
        ):
            raise LLMConnectionError(f"Connection error: {error_type}") from error

        # Safety filter
        if "safety" in error_str or "blocked" in error_str:
            raise LLMGenerationError(
                f"Content blocked by safety filter: {error_type}"
            ) from error

        # Context window
        if "context" in error_str and "window" in error_str:
            raise LLMGenerationError(
                f"Context window overflow: {error_type}"
            ) from error

        # Fallback: wrap as generation error
        raise LLMGenerationError(f"Generation failed: {error_type}: {error}") from error

    def embed(
        self,
        texts: List[str],
        *,
        timeout_seconds: int = 60,
    ) -> List[List[float]]:
        self._check_configured()

        if texts is None:
            raise TypeError("texts must be a list, got None.")
        if not isinstance(texts, list):
            raise TypeError(f"texts must be a list, got {type(texts).__name__}.")
        if len(texts) == 0:
            return []

        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise ValueError(
                    f"texts[{i}] must be a string, got " f"{type(text).__name__}."
                )
            if text == "":
                raise ValueError(f"texts[{i}] must not be empty.")

        try:
            result = self._client.models.embed_content(
                model=self._embedding_model,
                contents=texts,
            )
            return [e.values for e in result.embeddings]
        except Exception as e:
            self._map_sdk_error(e, 0)
            raise  # unreachable

    def count_tokens(self, text: str) -> int:
        self._check_configured()
        if not isinstance(text, str):
            raise TypeError(f"text must be a string, got {type(text).__name__}.")
        if text == "":
            return 0

        try:
            result = self._client.models.count_tokens(model=self._model, contents=text)
            return result.total_tokens
        except Exception:
            # Fallback: approximation
            logger.warning(
                "Native token counting failed, using approximation " "(chars/4)."
            )
            return max(1, len(text) // 4)

    def validate(self) -> bool:
        """Lightweight check using models.list() — no token cost."""
        self._check_configured()
        try:
            # Just verify the client can reach the API
            _ = list(self._client.models.list())
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._closed = True
        self._configured = False
        # genai.Client doesn't have persistent connections to close
        # but we clear the reference
        self._client = None
