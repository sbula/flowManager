from unittest.mock import MagicMock

import pytest

from src.flow.engine.tool_executor import ToolExecutor
from src.flow.tools.base import Tool, ToolContext, ToolError, ToolResult


class MockTool(Tool):
    name = "mock_tool"
    description = "A mock tool"
    input_schema = {}

    def run(self, args, context):
        if args.get("fail"):
            raise ToolError("Tool failed deliberately", code="MockError")
        if args.get("crash"):
            raise ValueError("Unexpected crash")
        return ToolResult(status="success", data={"echo": args.get("input")})


@pytest.fixture
def tool_executor():
    executor = ToolExecutor()
    executor.register_tool(MockTool())
    return executor


@pytest.fixture
def context():
    return ToolContext(
        service_root="/tmp",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-1",
        role="dev",
    )


def test_execute_success(tool_executor, context):
    """Verify successful execution."""
    result = tool_executor.execute("mock_tool", {"input": "hello"}, context)
    assert result.status == "success"
    assert result.data["echo"] == "hello"


def test_execute_tool_error(tool_executor, context):
    """Verify ToolError handling."""
    result = tool_executor.execute("mock_tool", {"fail": True}, context)
    assert result.status == "error"
    assert result.error["code"] == "MockError"


def test_execute_crash_handling(tool_executor, context):
    """Verify unexpected exception handling."""
    result = tool_executor.execute("mock_tool", {"crash": True}, context)
    assert result.status == "error"
    assert result.error["code"] == "InternalError"
    assert "Unexpected crash" in result.error["message"]


def test_execute_unknown_tool(tool_executor, context):
    """Verify unknown tool handling."""
    result = tool_executor.execute("unknown_tool", {}, context)
    assert result.status == "error"
    assert result.error["code"] == "ToolNotFound"
