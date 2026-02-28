class RootNotFoundError(Exception):
    pass


class SecurityError(Exception):
    pass


class RegistryError(Exception):
    pass


class CircuitBreakerError(Exception):
    """Raised when a task exceeds retry limits."""

    pass


class PayloadTooLargeError(Exception):
    """Raised when string payload exceeds OOM defense limits."""

    pass
