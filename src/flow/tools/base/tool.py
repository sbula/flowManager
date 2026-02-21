from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ToolContext:
    """
    Immutable context for tool execution.
    Contains service root, isolation level, allowed commands,
    token, volume ID, and role.
    """

    service_root: str
    isolation_level: str
    allowed_commands: List[str]
    access_token: str
    volume_id: str
    role: str


@dataclass
class ToolResult:
    """
    Standardized result from a tool execution.
    """

    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolError(Exception):
    """Base exception for all tool errors."""

    def __init__(
        self,
        message: str,
        code: str = "InternalError",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class Tool(ABC):
    """Abstract base class for all tools."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    required_role: Optional[str] = None

    @abstractmethod
    def run(self, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        """
        Execute the tool logic.
        WARNING: This method should NOT be called directly by the Engine.
        Use ToolExecutor.execute() instead to ensure safety wrapper.
        """
        pass
