from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AtomResult:
    def __init__(
        self, success: bool, message: str, exports: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.message = message
        self.exports = exports or {}


class Atom(ABC):
    """Base interface for all Atoms."""

    @abstractmethod
    def run(self, context: Dict[str, Any], **kwargs) -> AtomResult:
        pass


class ManualInterventionAtom(Atom):
    """Fallback atom when no specific atom is found."""

    def run(
        self, context: Dict[str, Any], task_name: str = "Unknown", **kwargs
    ) -> AtomResult:
        return AtomResult(False, f"Manual Intervention Required for task: {task_name}")


class FlowEngineAtom(Atom):
    """Pseudo-atom for Flow sub-workflows."""

    def run(self, context: Dict[str, Any], **kwargs) -> AtomResult:
        return AtomResult(True, "Flow dispatched")
