"""Custom exception hierarchy for the LLM Binding System.

Error classification per spec §6.2:
- ProviderNotConfiguredError: Lifecycle violation (use before configure)
- ProviderAlreadyConfiguredError: Double configure or configure after close
- ProviderConfigError: Structural config issues (missing model, bad URL)
- ProviderRegistrationError: Provider name mismatch or unknown provider
- ProfileNotFoundError: Unknown profile name in config
- FactoryClosedError: Factory used after close_all()
- MissingDependencyError: Provider SDK not installed
- LLMAuthError: Credential resolution failures (NOT retryable)
- LLMConnectionError: Network/API reachability (retryable)
- LLMRateLimitError: Quota exhaustion (retryable with backoff)
- LLMGenerationError: Model error, safety filter, empty response (conditional)
"""


class ProviderNotConfiguredError(RuntimeError):
    """Raised when generate/embed/count_tokens called before configure()
    or after close()."""

    pass


class ProviderAlreadyConfiguredError(RuntimeError):
    """Raised when configure() is called a second time, including after
    a failed first configure() or after close()."""

    pass


class ProviderConfigError(ValueError):
    """Structural config issues: missing 'model', invalid 'base_url',
    missing 'deployment_name' for Azure, model not found/deprecated."""

    pass


class ProviderRegistrationError(ValueError):
    """Provider name mismatch between adapter and registry, or
    unknown provider name in registry."""

    pass


class ProfileNotFoundError(KeyError):
    """Unknown profile name in flow_config.json."""

    pass


class FactoryClosedError(RuntimeError):
    """Factory used after close_all() has been called."""

    pass


class MissingDependencyError(ImportError):
    """Provider SDK not installed. Message includes install instructions."""

    pass


class LLMAuthError(RuntimeError):
    """Credential resolution failures: missing API key, expired token,
    revoked SSO. NOT retryable."""

    pass


class LLMConnectionError(ConnectionError):
    """Network/API reachability issues. Retryable."""

    pass


class LLMRateLimitError(RuntimeError):
    """Quota exhaustion (HTTP 429). Retryable with backoff."""

    pass


class LLMGenerationError(RuntimeError):
    """Model error, safety filter block, empty response, context window
    overflow. Conditionally retryable (overflow is NOT retryable)."""

    pass
