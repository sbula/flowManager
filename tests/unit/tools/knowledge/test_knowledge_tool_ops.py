import pytest
from unittest.mock import MagicMock
from src.flow.tools.knowledge import KnowledgeTool
from src.flow.tools.base import ToolContext

@pytest.fixture
def knowledge_tool():
    tool = KnowledgeTool()
    tool._client = MagicMock()
    return tool

@pytest.fixture
def context():
    return ToolContext(
        service_root="/app",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="fake-token",
        volume_id="vol-1",
        role="dev"
    )

def test_find_usage(knowledge_tool, context):
    """Verify find_usage delegates to client."""
    knowledge_tool._client.find_usage.return_value = [{"file": "a.py", "line": 10}]
    
    result = knowledge_tool.run({
        "operation": "find_usage",
        "symbol": "MyClass"
    }, context)
    
    assert result.status == "success"
    assert len(result.data["usages"]) == 1
    knowledge_tool._client.find_usage.assert_called_with("MyClass")

def test_get_related_tests(knowledge_tool, context):
    """Verify get_related_tests delegates to client."""
    knowledge_tool._client.get_related_tests.return_value = ["tests/test_a.py"]
    
    result = knowledge_tool.run({
        "operation": "get_related_tests",
        "file_path": "src/a.py"
    }, context)
    
    assert result.status == "success"
    assert "tests/test_a.py" in result.data["tests"]

def test_get_system_map(knowledge_tool, context):
    """Verify get_system_map delegates to client."""
    knowledge_tool._client.generate_map.return_value = {"services": []}
    
    result = knowledge_tool.run({
        "operation": "get_system_map"
    }, context)
    
    assert result.status == "success"
    assert "services" in result.data["map"]
    
def test_get_task_context(knowledge_tool, context):
    """Verify get_task_context delegates to client."""
    knowledge_tool._client.get_task_context.return_value = {"phase": "Integration"}
    
    result = knowledge_tool.run({
        "operation": "get_task_context",
        "task_id": "1.2"
    }, context)
    
    assert result.status == "success"
    assert result.data["context"]["phase"] == "Integration"
