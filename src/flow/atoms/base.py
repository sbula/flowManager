from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class AtomStatus(str, Enum):
    SUCCESS = "SUCCESS"  # Action completed as intended
    FAILED = "FAILED"  # Action failed permanently
    RETRY = "RETRY"  # Transient failure, Engine should retry based on strategy


class RetryStrategy(str, Enum):
    IMMEDIATE = "IMMEDIATE"  # Retry instantly without waiting
    BACKOFF = "BACKOFF"  # Exponential backoff


class AtomResult:
    def __init__(
        self,
        status: AtomStatus,
        message: str,
        exports: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
        retry_strategy: Optional[RetryStrategy] = None,
        compensating_action: Optional[Dict[str, Any]] = None,
    ):
        self.status = status
        self.message = message
        self.exports = exports or {}
        self.error = error
        self.retry_strategy = retry_strategy

    @property
    def success(self) -> bool:
        return self.status == AtomStatus.SUCCESS


class AtomConfig(BaseModel):
    """Base configuration for all Atoms."""

    model_config = ConfigDict(extra="allow")
    run_id: Optional[str] = None


class Atom(ABC):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.raw_config = config or {}
        self.config = self._parse_config(self.raw_config)

    def _parse_config(self, config: Dict[str, Any]) -> AtomConfig:
        """Override this in subclasses to return a specific AtomConfig."""
        return AtomConfig(**config)

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> AtomResult:
        """Executes the discrete unit of work."""
        pass

    def cleanup(self) -> None:
        """
        Graceful Teardown Hook (SIGINT/SIGTERM/Pause).
        """
        pass

    def get_hash(self) -> str:
        """
        Calculates a deterministic hash of the Atom's config for state reconciliation.
        Strips transient keys like timestamps and run_id.
        Handles zero-width characters (ZWNJ \u200b).
        Consistently handles floats that are whole numbers (1.0 -> 1) for T2.17.
        """
        import hashlib
        import json

        def normalize_floats_and_strings(obj: Any) -> Any:
            if isinstance(obj, float) and obj.is_integer():
                return int(obj)
            elif isinstance(obj, str):
                return obj.replace("\u200b", "")
            elif isinstance(obj, dict):
                return {
                    k: normalize_floats_and_strings(v)
                    for k, v in obj.items()
                    if k not in ("timestamp", "run_id")
                }
            elif isinstance(obj, list):
                return [normalize_floats_and_strings(v) for v in obj]
            return obj

        config_dict = self.config.model_dump()
        normalized = normalize_floats_and_strings(config_dict)
        payload = json.dumps(normalized, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ManualInterventionAtom(Atom):
    """
    Fallback atom when no suitable atom is found or manual intervention is required.
    """

    def run(self, context: Dict[str, Any]) -> AtomResult:
        return AtomResult(
            status=AtomStatus.FAILED, message="Manual intervention required"
        )


class FlowEngineAtom(Atom):
    """
    Atom representing an explicit flow step.
    """

    def run(self, context: Dict[str, Any]) -> AtomResult:
        return AtomResult(
            status=AtomStatus.SUCCESS, message="Flow engine step completed"
        )
