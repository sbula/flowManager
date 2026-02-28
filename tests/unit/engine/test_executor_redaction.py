import pytest

from src.flow.engine.tool_executor import ToolExecutor
from src.flow.tools.base import Tool, ToolContext, ToolResult


class LeakyTool(Tool):
    name = "leaky_tool"
    description = "Returns secrets"
    input_schema = {}

    def run(self, args, context):
        return ToolResult(
            status="success",
            data={
                "secret": "sk-1234567890abcdef1234567890abcdef",
                "nested": {"key": "ghp_1234567890abcdef1234567890abcdef"},
            },
        )


@pytest.fixture
def context():
    return ToolContext(
        service_root="/",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="",
        role="dev",
    )


def test_executor_redaction(context):
    executor = ToolExecutor()
    executor.register_tool(LeakyTool())

    result = executor.execute("leaky_tool", {}, context)

    assert result.status == "success"
    # Verify Redaction
    assert "[REDACTED_PATTERN]" in result.data["secret"]
    assert "sk-12345" not in result.data["secret"]

    assert "[REDACTED_PATTERN]" in result.data["nested"]["key"]
    assert "ghp_" not in result.data["nested"]["key"]
