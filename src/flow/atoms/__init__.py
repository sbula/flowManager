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
