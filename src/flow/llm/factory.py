"""LLM Factory — the ONLY way to obtain an LLM instance.

Located at: src/flow/llm/factory.py
See 01_06_llm_binding_spec.md §5 for full specification.
"""

import importlib
import logging
import threading
from typing import Any, Dict, Optional

from flow.llm.errors import (
    FactoryClosedError,
    ProfileNotFoundError,
    ProviderConfigError,
    ProviderRegistrationError,
)
from flow.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# Static provider registry mapping provider keys to adapter module paths
PROVIDER_REGISTRY: Dict[str, str] = {
    "gemini": "flow.llm.adapters.gemini_adapter.GeminiProvider",
    "openai": "flow.llm.adapters.openai_adapter.OpenAIProvider",
    "anthropic": "flow.llm.adapters.anthropic_adapter.AnthropicProvider",
    "ollama": "flow.llm.adapters.ollama_adapter.OllamaProvider",
    "azure_openai": "flow.llm.adapters.azure_openai_adapter.AzureOpenAIProvider",
}


class LLMFactory:
    """
    Factory for creating and caching LLM provider instances.

    Thread-safe singleton cache per profile name.
    See spec §5 for full lifecycle documentation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the factory.

        Args:
            config: The 'knowledge.profiles' section of flow_config.json.
                    If None, an empty dict is used.
        """
        self._config: Dict[str, Any] = config or {}
        self._cache: Dict[str, LLMProvider] = {}
        self._lock = threading.Lock()
        self._closed = False

    def create(self, profile_name: str) -> LLMProvider:
        """
        Get or create a configured LLMProvider for the given profile.

        Thread-safe. Returns cached instance if already created.

        Args:
            profile_name: The profile name from flow_config.json.

        Returns:
            A configured LLMProvider instance.

        Raises:
            FactoryClosedError: If close_all() was called.
            ProfileNotFoundError: If profile not in config.
            ProviderRegistrationError: If provider not in registry or
                                       name mismatch.
            ProviderConfigError: If profile missing 'provider' key.
        """
        with self._lock:
            if self._closed:
                raise FactoryClosedError(
                    "Factory has been shut down via close_all(). "
                    "Create a new LLMFactory instance to resume."
                )

            if profile_name in self._cache:
                return self._cache[profile_name]

            # Resolve profile from config
            if profile_name not in self._config:
                raise ProfileNotFoundError(
                    f"Profile '{profile_name}' not found in config. "
                    "Check flow_config.json 'knowledge.profiles' section."
                )

            profile = self._config[profile_name]

            # Extract provider name
            provider_key = profile.get("provider")
            if not provider_key:
                raise ProviderConfigError(
                    f"Profile '{profile_name}' is missing the 'provider' "
                    "key. Each profile must specify a provider."
                )

            if provider_key not in PROVIDER_REGISTRY:
                raise ProviderRegistrationError(
                    f"Unknown provider '{provider_key}' for profile "
                    f"'{profile_name}'. Known providers: "
                    f"{list(PROVIDER_REGISTRY.keys())}"
                )

            # Lazy-load the adapter class
            adapter_class = self._load_adapter_class(provider_key)

            # Instantiate and configure
            adapter = adapter_class()

            # Verify provider_name matches registry key
            if adapter.provider_name != provider_key:
                raise ProviderRegistrationError(
                    f"Adapter's provider_name '{adapter.provider_name}' "
                    f"does not match registry key '{provider_key}'. "
                    "This is a registration error."
                )

            # Prepare config for adapter
            adapter_config = dict(profile.get("config", {}))
            adapter_config["auth"] = profile.get("auth", {})
            adapter_config["profile_name"] = profile_name

            adapter.configure(adapter_config)

            self._cache[profile_name] = adapter
            return adapter

    def _load_adapter_class(self, provider_key: str) -> type:
        """
        Dynamically import the adapter class for the given provider.

        Raises:
            MissingDependencyError: If the provider module can't be imported.
        """
        from flow.llm.errors import MissingDependencyError

        module_path = PROVIDER_REGISTRY[provider_key]
        module_name, class_name = module_path.rsplit(".", 1)

        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise MissingDependencyError(
                f"Provider '{provider_key}' requires an SDK that is not "
                f"installed. Run 'poetry install -E {provider_key}' to "
                f"install it. Original error: {e}"
            ) from e

        return getattr(module, class_name)

    def reset(self, profile_name: str) -> None:
        """
        Evict a cached adapter, calling close() on it first.

        If profile_name was never created, this is a silent no-op.

        Args:
            profile_name: The profile to reset.

        Raises:
            FactoryClosedError: If close_all() was called.
        """
        with self._lock:
            if self._closed:
                raise FactoryClosedError(
                    "Factory has been shut down via close_all(). "
                    "Cannot reset on a closed factory."
                )

            adapter = self._cache.pop(profile_name, None)
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:
                    logger.warning(
                        "Error closing adapter for profile '%s' during reset",
                        profile_name,
                        exc_info=True,
                    )

    def reset_all(self) -> None:
        """
        Evict all cached adapters, calling close() on each.

        Raises:
            FactoryClosedError: If close_all() was called.
        """
        with self._lock:
            if self._closed:
                raise FactoryClosedError(
                    "Factory has been shut down via close_all(). "
                    "Cannot reset_all on a closed factory."
                )

            for profile_name, adapter in list(self._cache.items()):
                try:
                    adapter.close()
                except Exception:
                    logger.warning(
                        "Error closing adapter for profile '%s' " "during reset_all",
                        profile_name,
                        exc_info=True,
                    )
            self._cache.clear()

    def close_all(self) -> None:
        """
        Shut down: close all cached adapters and mark factory as closed.

        After this, create() raises FactoryClosedError.
        Per spec §5.2: Each adapter.close() has a 5s hard timeout.
        """
        with self._lock:
            if self._closed:
                return  # Idempotent

            import concurrent.futures

            for profile_name, adapter in list(self._cache.items()):
                # Apply 5s hard timeout per adapter
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                try:
                    future = executor.submit(adapter.close)
                    future.result(timeout=5.0)
                except concurrent.futures.TimeoutError:
                    logger.error(
                        "Adapter for profile '%s' close() timed out "
                        "after 5s. Abandoning.",
                        profile_name,
                    )
                except Exception:
                    logger.warning(
                        "Error closing adapter for profile '%s' " "during close_all",
                        profile_name,
                        exc_info=True,
                    )
                finally:
                    executor.shutdown(wait=False)

            self._cache.clear()
            self._closed = True
