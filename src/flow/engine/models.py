class RootNotFoundError(Exception):
    pass


class SecurityError(Exception):
    pass


class RegistryError(Exception):
    pass


class CircuitBreakerError(Exception):
    """Raised when a task exceeds retry limits."""

    pass
