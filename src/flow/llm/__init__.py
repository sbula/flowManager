"""LLM Binding & Selection System.

Provides a unified interface for all LLM provider interactions.
See 01_06_llm_binding_spec.md for full specification.
"""

from flow.llm.errors import (
    FactoryClosedError,
    LLMAuthError,
    LLMConnectionError,
    LLMGenerationError,
    LLMRateLimitError,
    MissingDependencyError,
    ProfileNotFoundError,
    ProviderAlreadyConfiguredError,
    ProviderConfigError,
    ProviderNotConfiguredError,
    ProviderRegistrationError,
)
from flow.llm.factory import LLMFactory
from flow.llm.provider import LLMProvider

__all__ = [
    "LLMProvider",
    "LLMFactory",
    "ProviderNotConfiguredError",
    "ProviderAlreadyConfiguredError",
    "ProviderConfigError",
    "ProviderRegistrationError",
    "ProfileNotFoundError",
    "FactoryClosedError",
    "MissingDependencyError",
    "LLMAuthError",
    "LLMConnectionError",
    "LLMRateLimitError",
    "LLMGenerationError",
]
