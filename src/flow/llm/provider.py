"""LLM Provider Abstract Base Class.

Located at: src/flow/llm/provider.py
All adapters MUST inherit from this ABC and implement all methods.
See 01_06_llm_binding_spec.md §3 for full specification.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from flow.llm.errors import ProviderNotConfiguredError  # noqa: F401 (re-exported for adapters)


class LLMProvider(ABC):
    """
    Abstract Base Class for all LLM Provider implementations.

    Lifecycle Contract:
      1. Factory instantiates the adapter via __init__() (no args).
      2. Factory calls configure(config) exactly ONCE.
      3. After configure() succeeds, generate()/embed()/count_tokens() are callable.
      4. Calling generate()/embed()/count_tokens() BEFORE configure() MUST raise
         ProviderNotConfiguredError. Even local tokenizers (e.g. tiktoken) require
         configure() to resolve which model's tokenizer to load.
      5. Calling configure() a SECOND time MUST raise ProviderAlreadyConfiguredError.
         This includes cases where the first configure() FAILED.
         A failed configure() poisons the adapter. The caller MUST discard it and
         obtain a fresh instance via Factory.reset() + Factory.create().
      5a. Resource Cleanup on configure() Failure: If configure() raises an
          exception after partially initializing SDK resources, the adapter MUST
          clean up those resources in its exception handler before re-raising.
      6. close() MAY be called to release SDK resources.
         After close(), calling generate()/embed()/count_tokens() MUST raise
         ProviderNotConfiguredError.
      7. close() is PERMANENT. After close(), calling configure()
         again MUST raise ProviderAlreadyConfiguredError.
      8. close() MUST be idempotent.

    Thread Safety:
      All implementations MUST be thread-safe.
    """

    _VALID_ROLES = {"system", "user", "assistant"}

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """The canonical unique identifier (e.g. 'gemini', 'openai').
        MUST match the registry key used by LLMFactory."""
        pass

    @property
    def embedding_dimensions(self) -> Optional[int]:
        """Returns the embedding dimensions for this provider's model,
        or None if unknown statically."""
        return None

    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> None:
        """
        Initialize the provider with a profile's config dict.

        The adapter MUST:
          - Resolve credentials from environment variables (see §4).
          - Initialize the underlying SDK client.
          - Validate that the credentials are well-formed (format check).

        Error Classification:
          - ProviderConfigError:           Structural config issues.
          - LLMAuthError:                  Credential resolution failures.
          - ProviderAlreadyConfiguredError: If called more than once.
        """
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        timeout_seconds: int = 120,
        **kwargs,
    ) -> str:
        """
        Synchronous text generation using the chat/messages paradigm.

        Args:
            messages: Ordered list of role/content dicts.
            timeout_seconds: Max wait time before aborting.
            **kwargs: Standardized overrides (temperature, max_tokens, etc.)
                      Unknown kwargs passed through to provider SDK.

        Returns:
            The generated text string. NEVER None, empty, or whitespace-only.

        Raises:
            ProviderNotConfiguredError: If configure() not called.
            ValueError:                If messages input fails validation.
            LLMConnectionError:        Network issues (retryable).
            LLMAuthError:              Invalid credentials (NOT retryable).
            LLMRateLimitError:         Quota exhaustion (retryable).
            LLMGenerationError:        Model error, safety filter, empty response.
            ProviderConfigError:       Model not found / deprecated.
            TimeoutError:              If timeout_seconds exceeded.
        """
        pass

    @abstractmethod
    def embed(
        self,
        texts: List[str],
        *,
        timeout_seconds: int = 60,
    ) -> List[List[float]]:
        """
        Batch embedding generation.

        Args:
            texts: List of strings to embed.
                   Empty list returns empty list without API call.
            timeout_seconds: Max wait time before aborting.

        Returns:
            List of embedding vectors. len(result) == len(texts).

        Raises:
            Same as generate(), plus:
            NotImplementedError: If provider doesn't support embeddings.
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Returns the token count for the given text.

        Args:
            text: A string to tokenize. Raises TypeError if not a string.
                  Returns 0 for empty strings.
        """
        pass

    def validate(self) -> bool:
        """
        Quick health check. Returns True if provider is reachable.

        Default implementation calls generate() with a trivial prompt.
        Adapter authors SHOULD override with a cheaper check.

        IMPORTANT: Default implementation costs tokens.
        """
        try:
            self.generate(
                [{"role": "user", "content": "ping"}],
                timeout_seconds=5,
                max_tokens=1,
            )
            return True
        except Exception:
            return False

    def close(self) -> None:
        """
        Release SDK resources (HTTP pools, background threads).

        After close(), generate()/embed() MUST raise ProviderNotConfiguredError.
        Default implementation: No-op.
        Must be idempotent.
        """
        pass
