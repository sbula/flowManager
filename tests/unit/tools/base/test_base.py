from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from src.flow.tools.base import Tool, ToolContext, ToolError, ToolResult


def test_tool_context_immutability():
    """T5.02: Verify ToolContext is immutable."""
    context = ToolContext(
        service_root="/app/services/trade-engine",
        isolation_level="STRICT",
        allowed_commands=["ls", "grep"],
        access_token="test-token",
        volume_id="vol-123",
        role="dev",
    )

    # Attempt to modify attributes should fail (dataclass frozen=True)
    with pytest.raises(Exception):  # FrozenInstanceError
        context.allowed_commands = ["rm"]

    with pytest.raises(Exception):
        context.service_root = "/etc"


def test_tool_result_schema():
    """Verify ToolResult structure and serialization."""
    # Success Case
    success = ToolResult(
        status="success", data={"files": ["a.py", "b.py"]}, metadata={"duration_ms": 10}
    )
    assert success.status == "success"
    assert success.data["files"] == ["a.py", "b.py"]
    assert success.error is None

    # Error Case
    error = ToolResult(
        status="error",
        error={"code": "FileNotFound", "message": "Missing file"},
        metadata={"duration_ms": 5},
    )
    assert error.status == "error"
    assert error.data is None
    assert error.error["code"] == "FileNotFound"


def test_base_tool_implementation():
    """Verify abstract base class enforcement."""

    class ConcreteTool(Tool):
        name = "concrete_tool"
        description = "A concrete tool"
        input_schema = {"type": "object"}

        def run(self, args: Dict[str, Any], context: ToolContext) -> ToolResult:
            return ToolResult(status="success", data={"echo": args["input"]})

    tool = ConcreteTool()
    context = ToolContext(
        service_root="/tmp",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="",
        role="dev",
    )

    result = tool.run({"input": "hello"}, context)
    assert result.status == "success"
    assert result.data["echo"] == "hello"


def test_tool_validation_error():
    """Verify ToolError hierarchy."""
    err = ToolError("Something went wrong", code="InternalError")
    assert str(err) == "Something went wrong"
    assert err.code == "InternalError"
