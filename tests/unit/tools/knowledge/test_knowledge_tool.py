import pytest
from unittest.mock import MagicMock, patch
from src.flow.tools.knowledge import KnowledgeTool
from src.flow.tools.base import ToolContext, ToolResult

@pytest.fixture
def knowledge_tool():
    return KnowledgeTool()

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

def test_check_status_ready(knowledge_tool, context):
    """T4.02: Verify RAG status check."""
    # Mock internal RAG client
    knowledge_tool._client = MagicMock()
    knowledge_tool._client.get_status.return_value = {"status": "ready"}
    
    result = knowledge_tool.run({"operation": "check_status"}, context)
    assert result.status == "success"
    assert result.data["status"] == "ready"

def test_search_knowledge_success(knowledge_tool, context):
    """T4.03: Verify search functionality."""
    knowledge_tool._client = MagicMock()
    knowledge_tool._client.search.return_value = [{"content": "snippet", "score": 0.9}]
    
    result = knowledge_tool.run({
        "operation": "search_knowledge", 
        "query": "event bus"
    }, context)
    
    assert result.status == "success"
    assert len(result.data["results"]) == 1

def test_unknown_operation(knowledge_tool, context):
    result = knowledge_tool.run({"operation": "invalid"}, context)
    assert result.status == "error"
    assert "Unknown operation" in result.error["message"]
