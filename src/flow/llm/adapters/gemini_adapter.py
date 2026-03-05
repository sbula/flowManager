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

    def _init_client(self, auth_method: str, auth: Dict) -> Any:
        """Dispatch to auth-specific client initializers with error-safe cleanup."""
        _AUTH_DISPATCH = {
            "api_key": lambda: self._configure_api_key(auth),
            "adc": lambda: self._configure_adc(),
            "vertex_adc": lambda: self._configure_vertex_adc(auth),
            "keyring": lambda: self._configure_keyring(auth),
            "none": lambda: genai.Client(api_key="dummy"),
        }
        if auth_method not in _AUTH_DISPATCH:
            raise ProviderConfigError(
                f"Unknown auth method '{auth_method}'. "
                "Supported: api_key, adc, vertex_adc, keyring, none."
            )
        client = None
        try:
            client = _AUTH_DISPATCH[auth_method]()
        except (LLMAuthError, ProviderConfigError, MissingDependencyError):
            if client is not None and hasattr(client, "close"):
                try:
                    client.close()
                except Exception:
                    pass
            raise
        except Exception as e:
            if client is not None and hasattr(client, "close"):
                try:
                    client.close()
                except Exception:
                    pass
            raise LLMAuthError(
                f"Failed to initialize Gemini client: {type(e).__name__}"
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

        auth = config.get("auth", {})
        auth_method = auth.get("method", "api_key")
        if not auth_method:
            auth_method = "api_key"
            logger.warning("No auth method specified, defaulting to 'api_key'")

        self._client = self._init_client(auth_method, auth)
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
    def _extract_generate_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and validate standardized kwargs for generate_content()."""
        gen_config: Dict[str, Any] = {}
        if "temperature" in kwargs:
            temp = kwargs.pop("temperature")
            if not isinstance(temp, (int, float)):
                raise ValueError(
                    f"temperature must be a number, got {type(temp).__name__}."
                )
            if temp < 0:
                raise ValueError("temperature must not be negative.")
            gen_config["temperature"] = temp
        if "max_tokens" in kwargs:
            gen_config["max_output_tokens"] = kwargs.pop("max_tokens")
        if "stop_sequences" in kwargs:
            stop = kwargs.pop("stop_sequences")
            if not isinstance(stop, list):
                raise ValueError("stop_sequences must be a list of strings.")
            gen_config["stop_sequences"] = stop
        if "top_p" in kwargs:
            gen_config["top_p"] = kwargs.pop("top_p")
        if "top_k" in kwargs:
            gen_config["top_k"] = kwargs.pop("top_k")
        return gen_config

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """Extract text from Gemini SDK response."""
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

        contents = self._messages_to_contents(messages)
        gen_config = self._extract_generate_kwargs(kwargs)

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
            raise  # unreachable

        text = self._extract_response_text(response)

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

    def _map_heuristic_error(self, error: Exception, error_str: str, error_type: str) -> None:
        """Heuristic error mapping by string matching."""
        _MATCHERS = [
            (lambda s: "401" in s or "403" in s or "api key" in s,
             lambda: LLMAuthError(f"Authentication failed: {error_type}")),
            (lambda s: "429" in s or "rate" in s or "quota" in s,
             lambda: LLMRateLimitError(f"Rate limit exceeded: {error_type}")),
            (lambda s: "404" in s or "not found" in s,
             lambda: ProviderConfigError(
                 f"Model '{self._model}' not found or deprecated. "
                 f"Update the profile config. ({error_type})")),
            (lambda s: any(kw in s for kw in (
                "connection", "network", "dns", "ssl", "timeout",
                "certificate", "502", "504", "jsondecodeerror")),
             lambda: LLMConnectionError(f"Connection error: {error_type}")),
            (lambda s: "safety" in s or "blocked" in s,
             lambda: LLMGenerationError(f"Content blocked by safety filter: {error_type}")),
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

        self._map_heuristic_error(error, error_str, error_type)

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
