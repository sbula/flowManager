"""Error types for the Skills & Personas module."""


class ConfigParseError(Exception):
    """Raised when a config file cannot be parsed or has structural issues."""
    pass


class SchemaVersionError(ConfigParseError):
    """Raised when schema_version is missing, wrong type, or unsupported."""
    pass


class RegistryError(Exception):
    """Raised when registry validation fails (metadata mismatch, missing deps, etc)."""
    pass


class ReservedKeyCollisionError(RegistryError):
    """Raised when exports contain keys shadowing reserved Engine keys."""
    pass


class PreconditionFailed(Exception):
    """Raised when capability collapse guard detects zero active capabilities."""
    pass
