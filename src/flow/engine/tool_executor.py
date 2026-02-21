import logging
import traceback
from typing import Any, Dict, List, Union

from ..security.redactor import StreamRedactor
from ..tools.base import Tool, ToolContext, ToolError, ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tools safely, handling exceptions, logging, and REDACTION.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._redactor = StreamRedactor()

    def register_tool(self, tool: Tool):
        """Register a tool instance."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def execute(
        self, tool_name: str, args: Dict[str, Any], context: ToolContext
    ) -> ToolResult:
        """
        Execute a tool by name with the given arguments and context.
        Wraps execution in a try/except block to ensure resilience.
        Applies Output Redaction to all results.
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                status="error",
                error={
                    "code": "ToolNotFound",
                    "message": f"Tool '{tool_name}' not found",
                },
            )

        try:
            # Check Role Access if not checked inside tool
            if tool.required_role and context.role != tool.required_role:
                return ToolResult(
                    status="error",
                    error={
                        "code": "PermissionDenied",
                        "message": f"Role '{context.role}' cannot access "
                        f"{tool.name}",
                    },
                )

            result = tool.run(args, context)
            return self._redact_result(result)

        except ToolError as e:
            # Expected tool error (validation, logic)
            logger.warning(f"ToolError in {tool_name}: {e}")
            result = ToolResult(
                status="error",
                error={"code": e.code, "message": str(e), "details": e.details},
            )
            return self._redact_result(result)

        except Exception as e:
            # Unexpected system error (crash)
            logger.error(f"InternalError in {tool_name}: {e}")
            logger.error(traceback.format_exc())
            result = ToolResult(
                status="error",
                error={
                    "code": "InternalError",
                    "message": f"Unexpected error: {str(e)}",
                },
            )
            return self._redact_result(result)

    def _redact_result(self, result: ToolResult) -> ToolResult:
        """Recursively redact string values in data and error fields."""
        if result.data:
            result.data = self._redact_struct(result.data)
        if result.error:
            result.error = self._redact_struct(result.error)
        return result

    def _redact_struct(self, data: Any) -> Any:
        """Helper to walk dict/list and redact strings."""
        if isinstance(data, str):
            return self._redactor.redact(data)
        elif isinstance(data, dict):
            return {k: self._redact_struct(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._redact_struct(i) for i in data]
        else:
            return data
